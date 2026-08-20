"""Fetch workshop data from a DOI-referenced public archive — per session, per
stage, local-first.

Each session is one or more **DOI-referenced deposits** on public archives
(figshare and UCLA Dataverse today; Zenodo is equally supported). We read the
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

It also **resumes**: within ``raw``, each file is checked against the archive's
size and MD5, so an interrupted multi-GB pull re-fetches only what's missing or
half-written. Re-running after a dropped connection is safe and cheap — it will
not mistake a partial download for a complete one.

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

Mirrors
-------
A session can list more than one deposit in :data:`SESSIONS`, tried in order.
A Dataverse candidate must both resolve **and** actually serve bytes, so a
primary whose storage has failed is skipped rather than chosen and then failed
on — see :func:`_deposit_ok` for why "the DOI resolves" is not enough. (The
byte probe is Dataverse-specific: pooch archives like Zenodo/figshare serve
files from the record itself and are taken on trust once they resolve.)
Publish a mirror with ``scripts/publish_figshare.py`` or
``scripts/publish_zenodo.py`` and add its DOI to the session's list.

Restoring a stage you broke
---------------------------
``--restore`` puts a processed stage back to the archive's canonical copy — the
"undo my run" path for when an interrupted or misconfigured step leaves output
that breaks the notebooks downstream::

    python scripts/get_data.py --restore                    # all processed stages
    python scripts/get_data.py --restore --what minian_out  # just Minian's output

Unlike ``--force``, this **empties the stage dir before extracting**, so nothing
from the broken run survives. It also reuses the bundle already sitting in
``data/.cache/`` when it matches what the archive published — the very first
``get_data.py`` run puts it there — so a restore is usually instant and needs no
network at all. Add ``--force`` to distrust the cache and re-download the bundle.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import time
import urllib.error
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
# Some archives (Harvard Dataverse among them) answer Python's default
# User-Agent with 403. Without this we would silently fall back to pooch for a
# perfectly good Dataverse instance and lose the native path's resume, progress
# and size verification — and skip the `_deposit_ok` health probe with it.
_HEADERS = {"User-Agent": "workshop-processing-and-analysis (github.com/miniscope)"}
_CHUNK = 1 << 20  # 1 MiB streaming chunk

# Raw video file types. With --skip-video these are left in the deposit and only
# the small raw files (timestamps, metadata) are pulled — enough for the capstone
# and any processed-only run, which never open the videos. The videos are only
# needed to *run* Minian (step 2) / eztrack (step 4) yourself.
_VIDEO_EXTS = {".avi", ".mp4", ".mkv", ".mov"}

# One or more deposits per session, tried in order; we read filenames + hashes
# from the DOI itself. Listing a mirror is what makes an archive outage
# survivable — and the check that picks between them is deliberately stricter
# than "does the DOI resolve" (see `_deposit_ok`). The live dataset's DOI is
# usually passed at workshop time via --doi rather than committed here.
# Ordered by measured download throughput, fastest first — because order is the
# only preference mechanism there is. A candidate is checked for *reachability*,
# never for speed, so a slow-but-alive archive listed first would simply be used
# and everyone would crawl. Provenance does not argue for a different order:
# every mirror is byte-identical and MANIFEST.txt proves it per file.
SESSIONS: dict[str, list[str]] = {
    "prerecorded": [
        "10.25346/S6SGHPCZ",                # UCLA Dataverse — ~9.2 MB/s measured
        "10.6084/m9.figshare.33289752.v1",  # figshare mirror — ~6.9 MB/s measured
        # Zenodo was measured at ~0.6 MB/s and dropped — see ORGANIZER.md.
        # scripts/publish_zenodo.py still works if it is ever wanted; its DOI
        # would belong here, at the end, since the list is ordered by speed.
    ],
    "live": [],                             # add its DOI here, or pass --doi
}

# The figshare DOI is version-pinned (`.v1`). An unpinned figshare DOI resolves
# to "latest", which would silently change what participants receive if a v2 is
# ever published — and it makes pooch warn on every single fetch.


def _nonempty(d: Path) -> bool:
    return d.is_dir() and any(d.iterdir())


def _get_json(url: str) -> dict:
    req = urllib.request.Request(url, headers=_HEADERS)
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as r:
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


def _deposit_ok(kind: str, registry: dict, ctx: str) -> bool:
    """Cheap check that a deposit actually serves *bytes*, not just metadata.

    An archive can list a dataset perfectly — file names, sizes, checksums, all
    correct — while its storage layer fails every single download. That is
    exactly how UCLA's archive went down, and it is why "the DOI resolves" is
    not enough to pick a mirror: the broken candidate would win every time and
    then fail at the first file.

    So ask for the first kilobyte of one file and read a byte of it. One
    request, and it distinguishes a healthy archive from a hollow one.
    """
    if not registry:
        return False

    if kind == "dataverse":
        # Smallest non-zero file: a 0-byte file would make the Range request a
        # spec-legal 416 on some backends and misreport a healthy archive as down.
        sizes = {n: int(registry[n].get("size") or 0) for n in registry}
        name = min(sizes, key=lambda n: sizes[n] or float("inf"))
        url = f"{ctx}/api/access/datafile/{registry[name]['id']}"
    else:
        # pooch archives get the same treatment. They used to be taken on
        # trust, which was survivable only while a Dataverse deposit was listed
        # first — the moment the list was reordered by speed, the trusted kind
        # became the *default* and the probe covered nothing. An embargoed or
        # unpublished figshare/Zenodo record resolves and lists files perfectly.
        try:
            from pooch.downloaders import doi_to_repository

            url = doi_to_repository(ctx).download_url(sorted(registry)[0])
        except Exception:
            return True  # cannot construct a probe; don't fail a usable mirror
    try:
        req = urllib.request.Request(url, headers={**_HEADERS, "Range": "bytes=0-1023"})
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as r:
            r.read(1)
        return True
    except urllib.error.HTTPError as e:
        # 416 = the storage layer looked at the file and answered; that is a
        # working archive (every file may be 0 bytes), not a hollow one.
        return e.code == 416
    except Exception:
        return False


def resolve_deposit(session: str, doi: str | None = None,
                    require_downloadable: bool = True,
                    ) -> tuple[str, str, dict, str]:
    """Find a usable deposit for *session*, returning ``(doi, kind, registry, ctx)``.

    Mirrors from :data:`SESSIONS` are tried in order and a deposit is only
    accepted if it both resolves *and* passes :func:`_deposit_ok`, so a primary
    whose storage is down is skipped rather than chosen and then failed on. An
    explicit *doi* bypasses the list entirely — that is the workshop-time
    override, and second-guessing it would be surprising.

    *require_downloadable* is what callers who only need the **file list** turn
    off — auditing local files against the archive's manifest reads no data, so
    a deposit whose storage is down still answers that question perfectly well.
    Demanding downloadability there would report a local problem where there is
    only a remote one.

    Raises ``LookupError`` naming what went wrong with each candidate, so a
    total failure says *why* every mirror was unusable instead of just "no DOI".
    """
    candidates = [doi] if doi else list(SESSIONS.get(session) or [])
    if not candidates:
        raise LookupError(
            f"no DOI known for session {session!r}. Pass --doi <DOI>, or add one to "
            f"SESSIONS[{session!r}] in scripts/get_data.py.")

    problems = []
    degraded = None  # resolves and lists files, but serves no bytes
    for candidate in candidates:
        if "XXXXXXX" in candidate:
            problems.append(f"doi:{candidate} — placeholder, not published yet")
            continue
        try:
            kind, registry, ctx = discover(candidate)
        except Exception as exc:
            problems.append(f"doi:{candidate} — unreadable ({type(exc).__name__}: {exc})")
            continue
        if not registry:
            # A deposit that lists nothing can satisfy nothing — and accepting
            # it here would mask a working mirror further down the list.
            problems.append(f"doi:{candidate} — resolves, but lists no files")
            continue
        if not _deposit_ok(kind, registry, ctx):
            problems.append(f"doi:{candidate} — resolves, but its files are not "
                            f"downloadable (archive storage outage)")
            degraded = degraded or (candidate, kind, registry, ctx)
            continue
        if candidate != candidates[0]:
            print(f"  NOTE primary deposit unusable; falling back to doi:{candidate}")
            for why in problems:
                print(f"       ({why})")
        return candidate, kind, registry, ctx

    if not require_downloadable and degraded:
        # Callers that only need the file *list* (an audit, or verifying local
        # files we already have) can work from a deposit whose storage is down.
        # Returning it here means the outage path costs one discovery pass, not
        # two, and never re-pays a stalled candidate's timeouts.
        return degraded

    raise LookupError(f"no usable deposit for session {session!r}:\n  "
                      + "\n  ".join(problems))


def _human(n: float) -> str:
    """Bytes as a short human string (e.g. ``9.4 GB``)."""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.1f} {unit}" if unit != "B" else f"{int(n)} B"
        n /= 1024


def _digest(path: Path, alg: str = "md5") -> str:
    """*alg* digest of *path*, read in chunks (files here run to hundreds of MB)."""
    h = hashlib.new(alg)
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(_CHUNK), b""):
            h.update(chunk)
    return h.hexdigest()


def _md5(path: Path) -> str:
    return _digest(path, "md5")


def _size_ok(path: Path, rec: dict) -> bool:
    """True if *path* exists and matches the size the archive published.

    Cheap (a ``stat``, no reading) and catches the truncated-by-Ctrl-C case,
    which is how an interrupted download actually fails.
    """
    if not path.is_file():
        return False
    want_size = int(rec.get("size") or 0)
    return path.stat().st_size == want_size if want_size else True


def _is_complete(path: Path, rec: dict) -> bool:
    """True if *path* already holds the archive's copy of *rec*.

    Size first, then the MD5 the archive published — which also catches the
    right-length-but-wrong-bytes case. Without this, a file left half-written by
    an interrupted run is indistinguishable from a finished one.
    """
    if not _size_ok(path, rec):
        return False
    want_md5 = rec.get("md5")
    if want_md5:
        return _md5(path) == want_md5
    # No hash published — size is all we can go on.
    return bool(int(rec.get("size") or 0))


def _matches_registry(path: Path, rec) -> bool:
    """True if *path* matches the archive's record for it, whatever its shape.

    The two archive kinds hand back different registry entries: Dataverse gives
    ``{"size", "md5"}``, pooch (Zenodo/figshare) gives a bare ``"alg:hexdigest"``
    string. Anything that inspects a registry entry has to handle both, or it
    works on one archive and raises ``AttributeError`` on the other.
    """
    if isinstance(rec, dict):
        return _is_complete(path, rec)
    alg, _, want = str(rec).partition(":")
    if not want:  # a bare digest with no algorithm prefix
        alg, want = "md5", str(rec)
    try:
        return _digest(path, alg) == want
    except ValueError:
        return True  # unknown algorithm — nothing we can check it against


def _dataverse_download(server: str, rec: dict, dest_path: Path, label: str = "") -> None:
    """Stream a Dataverse datafile to *dest_path*, verifying its MD5.

    Prints a live, single-line progress meter (downloaded / total, %) so a
    multi-GB raw pull doesn't look hung. *label* prefixes the line (e.g.
    ``[3/28] 12.avi``)."""
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    url = f"{server}/api/access/datafile/{rec['id']}"
    req = urllib.request.Request(url, headers=_HEADERS)
    total = int(rec.get("size") or 0)
    digest = hashlib.md5()
    done = 0
    # Redraw at most 4x/second, and not at all when stdout is not a tty: there
    # `\r` cannot overwrite, so an unthrottled meter writes ~9,300 lines and
    # ~550 KB of spew per raw pull into whatever the output is piped to.
    tty = sys.stdout.isatty()
    last_draw = 0.0
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as r, open(dest_path, "wb") as out:
        for chunk in iter(lambda: r.read(_CHUNK), b""):
            out.write(chunk)
            digest.update(chunk)
            done += len(chunk)
            now = time.monotonic()
            if tty and now - last_draw >= 0.25:
                last_draw = now
                pct = f"{done / total * 100:5.1f}%" if total else "  ?  "
                bar = f"{_human(done)}" + (f" / {_human(total)}" if total else "")
                sys.stdout.write(f"\r       {label} {pct}  {bar}        ")
                sys.stdout.flush()
    if tty:
        sys.stdout.write("\r" + " " * 79 + "\r")  # clear the progress line
        sys.stdout.flush()
    if rec["md5"] and digest.hexdigest() != rec["md5"]:
        dest_path.unlink(missing_ok=True)
        raise RuntimeError(f"MD5 mismatch for {dest_path.name}")
    print(f"       {label} done ({_human(done)})")


def _fetch(kind: str, ctx: str, registry: dict, names: list[str], dest: Path,
           force: bool = False) -> None:
    """Download *names* (a subset of *registry*) into *dest*, verified by hash.

    Files already present and matching the archive (size + MD5) are skipped, so
    an interrupted pull resumes where it left off instead of starting over —
    only what's missing or truncated is re-fetched. ``force`` re-downloads
    everything regardless.
    """
    dest.mkdir(parents=True, exist_ok=True)
    if kind == "dataverse":
        if not force:
            local = [n for n in names if (dest / n).is_file()]
            if local:
                print(f"       verifying {len(local)} local file(s) ...")
                have = {n for n in local if _is_complete(dest / n, registry[n])}
                if have:
                    print(f"       {len(have)} already complete - skipping.")
                names = [n for n in names if n not in have]
                if not names:
                    return
        total = sum(int(registry[n].get("size") or 0) for n in names)
        if total:
            print(f"       ({len(names)} files, {_human(total)} total)")
        for i, n in enumerate(names, 1):
            _dataverse_download(ctx, registry[n], dest / n, label=f"[{i}/{len(names)}] {n}")
    else:  # pooch (Zenodo/figshare/etc.)
        import pooch

        if force:
            # pooch re-downloads only what is absent or fails its hash, so a
            # forced refetch means removing the local copy first. Without this,
            # --force is silently a no-op on Zenodo-hosted sessions.
            for n in names:
                (dest / n).unlink(missing_ok=True)
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


def _clear_stage(dest: Path) -> None:
    """Empty *dest* so a bundle can be extracted into a clean directory.

    A restore has to *replace*, not overlay. ``extractall`` only overwrites the
    entries the bundle names and leaves everything else alone, so unpacking the
    canonical output on top of a half-finished run keeps that run's orphans. A
    ``.zarr`` store is a directory of chunk files, so a stray chunk is read back
    as real data — quieter, and worse, than the breakage we're recovering from.
    """
    # Guard the destructive part: this must be exactly a
    # data/sessions/<name>/<stage> dir, never a parent of one.
    root = DATA_ROOT.resolve()
    resolved = dest.resolve()
    if not resolved.is_relative_to(root) or len(resolved.relative_to(root).parts) != 2:
        raise RuntimeError(f"refusing to clear {dest} - not a stage dir under {DATA_ROOT}")
    if resolved.exists():
        shutil.rmtree(resolved)
    resolved.mkdir(parents=True)


def _bundle_path(session: str, stage: str) -> Path:
    """Where *session*'s ``<stage>.zip`` is cached.

    Scoped by session because every session publishes its bundles under the
    *same* names: in a flat cache, one session's ``minian_out.zip`` can be
    restored into another session's stage dir. With the archive up the checksum
    catches that; offline nothing does — and offline is exactly when a restore
    leans on the cache hardest.
    """
    return CACHE / session / f"{stage}.zip"


def _migrate_flat_cache() -> None:
    """Move pre-session-scoped bundles (``.cache/<stage>.zip``) under ``prerecorded/``.

    The flat layout predates the per-session cache, and ``prerecorded`` was the
    only published deposit for as long as it was in use — so that is whose
    bundles these are. Moving them beats re-downloading: they run to hundreds of
    MB, and they are precisely what a restore needs.
    """
    for stage in PROCESSED:
        legacy = CACHE / f"{stage}.zip"
        dest = _bundle_path("prerecorded", stage)
        if not legacy.is_file() or dest.exists():
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        legacy.rename(dest)
        print(f"  (cached {stage}.zip moved to data/.cache/prerecorded/)")


def _cached_bundle(session: str, stage: str, rec: dict | None) -> Path | None:
    """The cached bundle for *session*/*stage*, if we have one worth trusting.

    *rec* is the archive's registry entry (size + MD5) when we could reach the
    deposit, and ``None`` when we couldn't. Offline we take the cached bundle
    as-is: it is this session's by construction, and the only way it got here
    was passing this very check on the way in.
    """
    bundle = _bundle_path(session, stage)
    if not bundle.is_file():
        return None
    if rec is None:
        return bundle
    return bundle if _matches_registry(bundle, rec) else None


def raw_audit(session: str, doi: str | None = None, deep: bool = False,
              ) -> tuple[list[str], list[str]]:
    """Compare a session's local ``raw/`` against the archive's file list.

    Returns ``(missing, damaged)``: names the deposit has that aren't on disk,
    and names whose local copy doesn't match what was published. The default
    checks presence and, where the archive publishes a size, that the size
    matches — what an interrupted download breaks — and reads no file contents.
    *deep* verifies the published hash instead, which works for every archive
    kind (reads every byte, so roughly 10 s per 10 GB).

    Only the file *list* is fetched, never the data, so this is cheap enough for
    a pre-flight check. Raises if the deposit can't be read (offline, bad DOI)
    so callers can degrade to local-only checks instead of reporting a failure.
    """
    # Metadata is all an audit needs: it compares local files against the
    # published list and never downloads. A deposit whose storage has failed
    # still answers that perfectly, so don't demand downloadability here.
    _doi, kind, registry, _ctx = resolve_deposit(session, doi,
                                                 require_downloadable=False)
    # Registry entry shape is a property of the archive kind, decided once here
    # rather than sniffed per entry. Dataverse publishes a size, so a shallow
    # audit can spot truncation; pooch archives publish only a hash, so there
    # the shallow check degrades to presence and `deep` does the real work.
    has_size = kind == "dataverse"
    zips = {f"{st}.zip" for st in PROCESSED}
    raw_dir = DATA_ROOT / session / "raw"

    missing: list[str] = []
    damaged: list[str] = []
    for name, rec in registry.items():
        if name in zips:
            continue
        path = raw_dir / name
        if not path.is_file():
            missing.append(name)
        elif deep and not _matches_registry(path, rec):
            damaged.append(name)
        elif not deep and has_size and not _size_ok(path, rec):
            damaged.append(name)
    return sorted(missing), sorted(damaged)


def fetch_session(session: str, doi: str | None, stages: list[str], force: bool,
                  skip_video: bool = False) -> tuple[int, int]:
    """Fetch the requested *stages* of *session*.

    Returns ``(present, failed)``: how many stages are available afterward, and
    how many genuinely errored. A stage that simply isn't in the deposit is
    *skipped*, not failed — only download/extract errors (and an unreadable
    deposit) count toward *failed*.
    """
    _migrate_flat_cache()

    # Local-first, and settled *before* any archive is contacted. Keeping a
    # stage you already have is a purely local decision, so an archive outage
    # must not turn it into a failure — someone whose data is already on disk
    # has no business being blocked by a dead server.
    #
    # `raw` never short-circuits here: it comes from the archive file-by-file,
    # so its completeness is verifiable against the registry, and _fetch re-pulls
    # only what is missing or truncated. A blanket "dir is non-empty -> KEEP"
    # would mistake an interrupted pull for a finished one and leave the session
    # quietly incomplete. Processed stages stay coarse: a local dir there may be
    # your own upstream output, which is the whole point of local-first.
    ok = failed = 0
    todo = []
    for stage in stages:
        if stage != "raw" and _nonempty(DATA_ROOT / session / stage) and not force:
            print(f"  KEEP {session}/{stage}: local data present "
                  f"(--force to re-download; --restore to replace a broken run).")
            ok += 1
        else:
            todo.append(stage)
    if not todo:
        return ok, failed

    # require_downloadable=False so that when no deposit serves bytes we still
    # get one that lists files: _fetch skips everything already matching the
    # registry, so a raw/ that is complete on disk verifies and KEEPs during an
    # outage instead of failing. Stages that genuinely need bytes still FAIL,
    # per stage, with the real download error.
    try:
        doi, kind, registry, ctx = resolve_deposit(session, doi,
                                                   require_downloadable=False)
    except LookupError as exc:
        print(f"  FAIL {session}: {exc}")
        return ok, failed + len(todo)
    print(f"  using doi:{doi} ({kind})")

    zip_for = {st: f"{st}.zip" for st in PROCESSED}
    raw_files = [f for f in registry if f not in set(zip_for.values())]

    for stage in todo:
        dest = DATA_ROOT / session / stage
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
                _fetch(kind, ctx, registry, files, dest, force=force)
            else:
                zname = zip_for[stage]
                if zname not in registry:
                    print(f"  SKIP {session}/{stage}: {zname} not in this deposit yet.")
                    continue
                print(f"  GET  {session}/{stage}: {zname}")
                _fetch(kind, ctx, registry, [zname], CACHE / session, force=force)
                dest.mkdir(parents=True, exist_ok=True)
                with zipfile.ZipFile(_bundle_path(session, stage)) as z:
                    _safe_extract(z, dest)
        except Exception as exc:
            print(f"  FAIL {session}/{stage}: {type(exc).__name__}: {exc}")
            failed += 1
            continue
        print(f"       -> data/sessions/{session}/{stage}/")
        ok += 1
    return ok, failed


def restore_session(session: str, stages: list[str], doi: str | None = None,
                    force: bool = False) -> tuple[int, int]:
    """Put processed *stages* of *session* back to the archive's canonical copy.

    The recovery path: empty the stage dir and rebuild it from the bundle the
    archive published, so a participant whose run went sideways ends up
    byte-identical to everyone else and the downstream notebooks open again.

    The bundle is reused from ``data/.cache/`` whenever it matches what the
    archive published, which is the normal case — the first ``get_data.py`` run
    already cached it. That makes a restore quick and fully offline, which
    matters most in exactly the situation it's for: a room full of people on one
    network. ``force`` distrusts the cache and re-downloads instead.

    Returns ``(restored, failed)``.
    """
    _migrate_flat_cache()
    kind = ctx = None
    registry: dict | None = None
    try:
        doi, kind, registry, ctx = resolve_deposit(session, doi)
    except LookupError as exc:
        # No usable deposit is not fatal here: the cached bundle is the whole
        # point of a restore, and it is exactly when the archive is down that
        # someone needs one. Say why, in full, then fall through to the cache.
        for i, line in enumerate(str(exc).splitlines()):
            print(f"  NOTE {line}" if i == 0 else f"       {line.strip()}")
        print(f"       restoring from the local cache alone.")

    restored = failed = 0
    for stage in stages:
        if stage == "raw":
            # raw is published file-by-file, so there's no bundle to restore
            # from - and it needs none: a plain fetch already checks every raw
            # file against the archive and re-pulls whatever is missing or
            # truncated. Point people at that rather than silently doing nothing.
            print("  SKIP raw: not a bundle - re-run without --restore to repair raw files.")
            continue

        zname = f"{stage}.zip"
        rec = registry.get(zname) if registry is not None else None
        if registry is not None and rec is None:
            print(f"  SKIP {session}/{stage}: {zname} not in this deposit.")
            continue

        bundle = None if force else _cached_bundle(session, stage, rec)
        try:
            if bundle is None:
                if registry is None:
                    print(f"  FAIL {session}/{stage}: no usable cached {zname} and the "
                          f"archive is unreachable - reconnect and retry.")
                    failed += 1
                    continue
                why = "forced" if force else "not cached"
                print(f"  GET  {session}/{stage}: {zname} ({why})")
                _fetch(kind, ctx, registry, [zname], CACHE / session, force=True)
                bundle = _bundle_path(session, stage)
            else:
                print(f"  USE  {session}/{stage}: cached {zname}"
                      f"{'' if rec else ' (unverified - archive unreachable)'}")

            dest = DATA_ROOT / session / stage
            _clear_stage(dest)
            with zipfile.ZipFile(bundle) as z:
                _safe_extract(z, dest)
        except Exception as exc:
            print(f"  FAIL {session}/{stage}: {type(exc).__name__}: {exc}")
            failed += 1
            continue
        print(f"       -> restored data/sessions/{session}/{stage}/")
        restored += 1
    return restored, failed


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Fetch workshop data from a DOI (Dataverse/Zenodo), local-first.")
    ap.add_argument("--session", default="prerecorded", choices=list(SESSIONS))
    ap.add_argument("--what", default=None, choices=list(GROUPS),
                    help="a group (all/raw/processed) or a single stage "
                         "(minian_out/deconv_out/eztrack_out). Defaults to 'all', "
                         "or to 'processed' with --restore")
    ap.add_argument("--doi", help="override the session DOI (e.g. the live dataset published "
                                   "during the workshop)")
    ap.add_argument("--force", action="store_true", help="re-download even if local data exists")
    ap.add_argument("--restore", action="store_true",
                    help="put processed stage(s) back to the archive's copy: empty the stage "
                         "dir and re-extract the published bundle, so nothing from a broken "
                         "run survives. Reuses the bundle in data/.cache/ when it matches, so "
                         "this is usually instant and works offline. Use this when your own "
                         "output breaks the notebooks downstream; add --force to re-download "
                         "the bundle instead of trusting the cache")
    ap.add_argument("--skip-video", action="store_true",
                    help="when fetching raw, skip the large video files (.avi/.mp4) and "
                         "grab only timestamps + metadata — enough for the capstone and any "
                         "processed-only run (the videos are only needed to run Minian/eztrack)")
    args = ap.parse_args()

    what = args.what or ("processed" if args.restore else "all")
    stages = GROUPS[what]

    if args.restore:
        # Deliberately ahead of the DOI checks below: a cache-backed restore is
        # the whole point and must work with no DOI and no network.
        print(f"Restoring session '{args.session}' ({what}: {', '.join(stages)}) "
              f"to the archive's copy ...")
        ok, failed = restore_session(args.session, stages, args.doi, args.force)
        print(f"\n{ok} stage(s) restored under data/sessions/{args.session}/")
        return 1 if failed else 0

    print(f"Fetching session '{args.session}' "
          f"({what}: {', '.join(stages)}) ...")
    ok, failed = fetch_session(args.session, args.doi, stages, args.force, args.skip_video)
    print(f"\n{ok}/{len(stages)} stage(s) available under data/sessions/{args.session}/")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
