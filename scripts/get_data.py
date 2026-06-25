"""Fetch workshop data from Zenodo with pooch — per session, per stage, local-first.

Each session is **one Zenodo deposit**. We **auto-discover** its files and their
checksums straight from the DOI (``pooch.load_registry_from_doi``), so the only
thing this script needs to know is the DOI — no hardcoded filenames or hashes.
A deposit holds:

* the **raw** recording as individual files (``behavior.mp4``, ``*.avi``,
  ``*_timestamp.csv``, ``*_metaData.json`` — anything that isn't a stage zip),
  downloaded straight into ``raw/``; and
* one zip per **processed** stage (``minian_out.zip`` / ``deconv_out.zip`` /
  ``eztrack_out.zip``), extracted into that stage's dir.

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

    python scripts/get_data.py --session live --doi 10.5281/zenodo.NNNNNN

Examples
--------
    python scripts/get_data.py                          # prerecorded, all stages
    python scripts/get_data.py --what raw               # just the raw recording
    python scripts/get_data.py --what processed         # minian+deconv+eztrack outputs
    python scripts/get_data.py --session live --doi ... # the workshop recording
    python scripts/get_data.py --force                  # re-download even if present
"""

from __future__ import annotations

import argparse
import sys
import zipfile
from pathlib import Path

import pooch

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_ROOT = REPO_ROOT / "data" / "sessions"
CACHE = REPO_ROOT / "data" / ".cache"

PROCESSED = ["minian_out", "deconv_out", "eztrack_out"]
STAGE_KEYS = ["raw", *PROCESSED]
GROUPS = {"raw": ["raw"], "processed": PROCESSED, "all": STAGE_KEYS}

# One Zenodo deposit per session; we read filenames + hashes from the DOI itself.
# Fill a DOI once its deposit is published. The live dataset's DOI is usually
# passed at workshop time via --doi rather than committed here.
SESSIONS: dict[str, str | None] = {
    "prerecorded": "10.5281/zenodo.XXXXXXX",  # TODO: backup dataset DOI (once published)
    "live": None,                              # set here if you publish it, or pass --doi
}


def _nonempty(d: Path) -> bool:
    return d.is_dir() and any(d.iterdir())


def _safe_extract(z: zipfile.ZipFile, dest: Path) -> None:
    """Extract *z* into *dest*, refusing any entry that escapes *dest* (Zip Slip)."""
    dest = dest.resolve()
    for name in z.namelist():
        target = (dest / name).resolve()
        if not target.is_relative_to(dest):
            raise RuntimeError(f"unsafe path in archive: {name!r}")
    z.extractall(dest)


def discover(doi: str) -> dict[str, str]:
    """Return ``{filename: hash}`` for every file in the Zenodo deposit at *doi*."""
    p = pooch.create(path=CACHE, base_url=f"doi:{doi}/", registry=None)
    p.load_registry_from_doi()  # queries the Zenodo API for the file list + checksums
    return dict(p.registry)


def _fetch_into(doi: str, registry: dict[str, str], names: list[str], dest: Path) -> None:
    """Download *names* (a subset of *registry*) into *dest*, verified by hash."""
    dest.mkdir(parents=True, exist_ok=True)
    p = pooch.create(
        path=dest, base_url=f"doi:{doi}/",
        registry={n: registry[n] for n in names},
    )
    for n in names:
        p.fetch(n)


def fetch_session(session: str, doi: str, stages: list[str], force: bool) -> tuple[int, int]:
    """Fetch the requested *stages* of *session*.

    Returns ``(present, failed)``: how many stages are available afterward, and
    how many genuinely errored. A stage that simply isn't in the deposit is
    *skipped*, not failed — only download/extract errors (and an unreadable
    deposit) count toward *failed*.
    """
    try:
        registry = discover(doi)
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
                if not raw_files:
                    print(f"  SKIP {session}/raw: no raw files in this deposit.")
                    continue
                print(f"  GET  {session}/raw: {len(raw_files)} files")
                _fetch_into(doi, registry, raw_files, dest)
            else:
                zname = zip_for[stage]
                if zname not in registry:
                    print(f"  SKIP {session}/{stage}: {zname} not in this deposit yet.")
                    continue
                print(f"  GET  {session}/{stage}: {zname}")
                _fetch_into(doi, registry, [zname], CACHE)
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
    ap = argparse.ArgumentParser(description="Fetch workshop data from Zenodo (local-first).")
    ap.add_argument("--session", default="prerecorded", choices=list(SESSIONS))
    ap.add_argument("--what", default="all", choices=list(GROUPS))
    ap.add_argument("--doi", help="override the session DOI (e.g. the live dataset published "
                                   "during the workshop)")
    ap.add_argument("--force", action="store_true", help="re-download even if local data exists")
    args = ap.parse_args()

    doi = args.doi or SESSIONS.get(args.session)
    if not doi:
        print(f"No DOI for session '{args.session}'. Publish its deposit and set "
              f"SESSIONS['{args.session}'] in this script, or pass --doi 10.5281/zenodo.NNNNNN.")
        return 1
    if "XXXXXXX" in doi:
        print(f"Session '{args.session}' has a placeholder DOI ({doi}) — its dataset "
              f"isn't published yet.\nPass a real one with --doi 10.5281/zenodo.NNNNNN, "
              f"or wait for the workshop release.")
        return 1

    stages = GROUPS[args.what]
    print(f"Fetching session '{args.session}' from doi:{doi} "
          f"({args.what}: {', '.join(stages)}) ...")
    ok, failed = fetch_session(args.session, doi, stages, args.force)
    print(f"\n{ok}/{len(stages)} stage(s) available under data/sessions/{args.session}/")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
