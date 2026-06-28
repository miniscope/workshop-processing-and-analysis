"""Fetch workshop data from a DOI-referenced public archive — per session, per
stage, local-first.

Each session is **one DOI-referenced dataset** on a public archive (UCLA
Dataverse today; Zenodo is equally supported for future deposits). We read the
file list and checksums straight from the archive, so the only thing this script
needs to know is the DOI — no hardcoded filenames or hashes. A dataset holds:

* the **raw** recording as individual files (``behavior.mp4``, ``*.avi``,
  ``*_timestamp.csv``, ``*_metaData.json`` — anything that isn't a stage zip),
  downloaded straight into ``raw/``; and
* one zip per **processed** stage (``minian_out.zip`` / ``deconv_out.zip`` /
  ``eztrack_out.zip``), extracted into that stage's dir.

How we resolve a DOI depends on where it lives:

* **Dataverse** — read the file list from the Dataverse native API directly.
  (pooch resolves a DOI by *following the doi.org redirect*, and UCLA
  Dataverse's ``/citation`` landing redirect trips that up — it mangles the
  host — so we don't route Dataverse through pooch.)
* **Zenodo / figshare / etc.** — fall back to ``pooch.load_registry_from_doi``,
  which handles those fine.

Data lands under ``data/sessions/<name>/``::

    raw/         miniscope video, behavior video, neural + behavior timestamps
    minian_out/  Minian output   (step 2)
    deconv_out/  calab output    (step 3)
    eztrack_out/ eztrack output  (step 4)

The fetch is **local-first**: a stage you already produced (by running the
upstream step) is kept, and only missing stages are downloaded. A stage that
isn't in the deposit yet is simply skipped.

The **live** dataset is published *during* the workshop, so its DOI isn't baked
in — pass it at fetch time with ``--doi`` (no code edit, no ``git pull``):

    python scripts/get_data.py --session live --doi <DOI>

Examples
--------
    python scripts/get_data.py                          # prerecorded, all stages
    python scripts/get_data.py --what raw               # just the raw recording
    python scripts/get_data.py --what processed         # minian+deconv+eztrack outputs
    python scripts/get_data.py --what minian_out        # a single processed stage
    python scripts/get_data.py --session live --doi ... # the workshop recording
    python scripts/get_data.py --force                  # re-download even if present

``--what`` accepts a group (``raw`` / ``processed`` / ``all``) or a single stage
name (``minian_out`` / ``deconv_out`` / ``eztrack_out``). Pulling one stage is
handy when you produced the others yourself — e.g. you tracked behavior in
eztrack but want the canonical Minian output: ``--what minian_out``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import urllib.request
import zipfile
from pathlib import Path
from urllib.parse import urlsplit

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_ROOT = REPO_ROOT / "data" / "sessions"
CACHE = REPO_ROOT / "data" / ".cache"

PROCESSED = ["minian_out", "deconv_out", "eztrack_out"]
STAGE_KEYS = ["raw", *PROCESSED]
# --what accepts a group (all/raw/processed) or a single stage name. The
# per-stage keys map to a one-element list, so you can pull just one stage
# (e.g. --what minian_out) when you produced the others yourself.
GROUPS = {
    "all": STAGE_KEYS,
    "raw": ["raw"],
    "processed": PROCESSED,
    **{stage: [stage] for stage in PROCESSED},
}

_TIMEOUT = 60  # seconds, per request
_CHUNK = 1 << 20  # 1 MiB streaming chunk

# Raw video file types. With --skip-video these are left in the deposit and only
# the small raw files (timestamps, metadata) are pulled — enough for the capstone
# and any processed-only run, which never open the videos. The videos are only
# needed to *run* Minian (step 2) / eztrack (step 4) yourself.
_VIDEO_EXTS = {".avi", ".mp4", ".mkv", ".mov"}

# One dataset (DOI) per session; we read filenames + hashes from the DOI itself.
# Fill a DOI once its dataset is published. The live dataset's DOI is usually
# passed at workshop time via --doi rather than committed here.
SESSIONS: dict[str, str | None] = {
    "prerecorded": "10.25346/S6SGHPCZ",  # UCLA Dataverse — published
    "live": None,                        # set here if you publish it, or pass --doi
}


def _nonempty(d: Path) -> bool:
    return d.is_dir() and any(d.iterdir())


def _get_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=_TIMEOUT) as r:
        return json.load(r)


def _landing(doi: str) -> str:
    """The DOI's registered landing URL (from DataCite), e.g. the archive page."""
    meta = _get_json(f"https://api.datacite.org/dois/{doi}")
    return meta["data"]["attributes"]["url"]


def _dataverse_registry(server: str, doi: str) -> dict[str, dict]:
    """``{filename: {"id", "md5"}}`` from a Dataverse instance's native API."""
    api = f"{server}/api/datasets/:persistentId?persistentId=doi:{doi}"
    data = _get_json(api)
    reg: dict[str, dict] = {}
    for entry in data["data"]["latestVersion"]["files"]:
        df = entry["dataFile"]
        label = entry.get("directoryLabel")  # Dataverse folder, if any
        name = f"{label}/{df['filename']}" if label else df["filename"]
        reg[name] = {"id": df["id"], "md5": df.get("md5", ""),
                     "size": df.get("filesize", 0)}
    return reg


def discover(doi: str) -> tuple[str, dict, str]:
    """Resolve *doi* to its file list.

    Returns ``(kind, registry, ctx)``:

    * ``kind == "dataverse"``: ``registry`` is ``{name: {"id", "md5"}}`` and
      ``ctx`` is the Dataverse base URL (download via the native API).
    * ``kind == "pooch"``: ``registry`` is ``{name: hash}`` and ``ctx`` is the
      DOI (download via pooch — Zenodo/figshare/etc.).
    """
    parts = urlsplit(_landing(doi))
    server = f"{parts.scheme}://{parts.netloc}"
    try:
        return "dataverse", _dataverse_registry(server, doi), server
    except Exception:
        # Not a Dataverse instance (or no native API) — let pooch handle it.
        import pooch  # lazy: only needed for non-Dataverse archives

        p = pooch.create(path=CACHE, base_url=f"doi:{doi}/", registry=None)
        p.load_registry_from_doi()
        return "pooch", dict(p.registry), doi


def _human(n: float) -> str:
    """Bytes as a short human string (e.g. ``9.4 GB``)."""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.1f} {unit}" if unit != "B" else f"{int(n)} B"
        n /= 1024


def _dataverse_download(server: str, rec: dict, dest_path: Path, label: str = "") -> None:
    """Stream a Dataverse datafile to *dest_path*, verifying its MD5.

    Prints a live, single-line progress meter (downloaded / total, %) so a
    multi-GB raw pull doesn't look hung. *label* prefixes the line (e.g.
    ``[3/28] 12.avi``)."""
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    url = f"{server}/api/access/datafile/{rec['id']}"
    total = int(rec.get("size") or 0)
    digest = hashlib.md5()
    done = 0
    with urllib.request.urlopen(url, timeout=_TIMEOUT) as r, open(dest_path, "wb") as out:
        for chunk in iter(lambda: r.read(_CHUNK), b""):
            out.write(chunk)
            digest.update(chunk)
            done += len(chunk)
            pct = f"{done / total * 100:5.1f}%" if total else "  ?  "
            bar = f"{_human(done)}" + (f" / {_human(total)}" if total else "")
            sys.stdout.write(f"\r       {label} {pct}  {bar}        ")
            sys.stdout.flush()
    sys.stdout.write("\r" + " " * 79 + "\r")  # clear the progress line
    sys.stdout.flush()
    if rec["md5"] and digest.hexdigest() != rec["md5"]:
        dest_path.unlink(missing_ok=True)
        raise RuntimeError(f"MD5 mismatch for {dest_path.name}")
    print(f"       {label} done ({_human(done)})")


def _fetch(kind: str, ctx: str, registry: dict, names: list[str], dest: Path) -> None:
    """Download *names* (a subset of *registry*) into *dest*, verified by hash."""
    dest.mkdir(parents=True, exist_ok=True)
    if kind == "dataverse":
        total = sum(int(registry[n].get("size") or 0) for n in names)
        if total:
            print(f"       ({len(names)} files, {_human(total)} total)")
        for i, n in enumerate(names, 1):
            _dataverse_download(ctx, registry[n], dest / n, label=f"[{i}/{len(names)}] {n}")
    else:  # pooch (Zenodo/figshare/etc.)
        import pooch

        p = pooch.create(
            path=dest, base_url=f"doi:{ctx}/",
            registry={n: registry[n] for n in names},
        )
        for n in names:
            p.fetch(n)


def _safe_extract(z: zipfile.ZipFile, dest: Path) -> None:
    """Extract *z* into *dest*, refusing any entry that escapes *dest* (Zip Slip)."""
    dest = dest.resolve()
    for name in z.namelist():
        target = (dest / name).resolve()
        if not target.is_relative_to(dest):
            raise RuntimeError(f"unsafe path in archive: {name!r}")
    z.extractall(dest)


def fetch_session(session: str, doi: str, stages: list[str], force: bool,
                  skip_video: bool = False) -> tuple[int, int]:
    """Fetch the requested *stages* of *session*.

    Returns ``(present, failed)``: how many stages are available afterward, and
    how many genuinely errored. A stage that simply isn't in the deposit is
    *skipped*, not failed — only download/extract errors (and an unreadable
    deposit) count toward *failed*.
    """
    try:
        kind, registry, ctx = discover(doi)
    except Exception as exc:  # bad/unpublished DOI, no network, API change
        print(f"  FAIL {session}: could not read deposit at doi:{doi} "
              f"({type(exc).__name__}: {exc})")
        return 0, len(stages)

    zip_for = {st: f"{st}.zip" for st in PROCESSED}
    raw_files = [f for f in registry if f not in set(zip_for.values())]

    ok = failed = 0
    for stage in stages:
        dest = DATA_ROOT / session / stage
        if _nonempty(dest) and not force:
            print(f"  KEEP {session}/{stage}: local data present (use --force to re-download).")
            ok += 1
            continue
        try:
            if stage == "raw":
                files = raw_files
                if skip_video:
                    files = [f for f in files
                             if Path(f).suffix.lower() not in _VIDEO_EXTS]
                if not files:
                    why = ("only video in this deposit (skipped)" if skip_video and raw_files
                           else "no raw files in this deposit")
                    print(f"  SKIP {session}/raw: {why}.")
                    continue
                note = "  (timestamps/metadata only; skipping video)" if skip_video else ""
                print(f"  GET  {session}/raw: {len(files)} files{note}")
                _fetch(kind, ctx, registry, files, dest)
            else:
                zname = zip_for[stage]
                if zname not in registry:
                    print(f"  SKIP {session}/{stage}: {zname} not in this deposit yet.")
                    continue
                print(f"  GET  {session}/{stage}: {zname}")
                _fetch(kind, ctx, registry, [zname], CACHE)
                dest.mkdir(parents=True, exist_ok=True)
                with zipfile.ZipFile(CACHE / zname) as z:
                    _safe_extract(z, dest)
        except Exception as exc:
            print(f"  FAIL {session}/{stage}: {type(exc).__name__}: {exc}")
            failed += 1
            continue
        print(f"       -> data/sessions/{session}/{stage}/")
        ok += 1
    return ok, failed


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Fetch workshop data from a DOI (Dataverse/Zenodo), local-first.")
    ap.add_argument("--session", default="prerecorded", choices=list(SESSIONS))
    ap.add_argument("--what", default="all", choices=list(GROUPS),
                    help="a group (all/raw/processed) or a single stage "
                         "(minian_out/deconv_out/eztrack_out)")
    ap.add_argument("--doi", help="override the session DOI (e.g. the live dataset published "
                                   "during the workshop)")
    ap.add_argument("--force", action="store_true", help="re-download even if local data exists")
    ap.add_argument("--skip-video", action="store_true",
                    help="when fetching raw, skip the large video files (.avi/.mp4) and "
                         "grab only timestamps + metadata — enough for the capstone and any "
                         "processed-only run (the videos are only needed to run Minian/eztrack)")
    args = ap.parse_args()

    doi = args.doi or SESSIONS.get(args.session)
    if not doi:
        print(f"No DOI for session '{args.session}'. Publish its dataset and set "
              f"SESSIONS['{args.session}'] in this script, or pass --doi <DOI>.")
        return 1
    if "XXXXXXX" in doi:
        print(f"Session '{args.session}' has a placeholder DOI ({doi}) — its dataset "
              f"isn't published yet.\nPass a real one with --doi <DOI>, "
              f"or wait for the workshop release.")
        return 1

    stages = GROUPS[args.what]
    print(f"Fetching session '{args.session}' from doi:{doi} "
          f"({args.what}: {', '.join(stages)}) ...")
    ok, failed = fetch_session(args.session, doi, stages, args.force, args.skip_video)
    print(f"\n{ok}/{len(stages)} stage(s) available under data/sessions/{args.session}/")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
