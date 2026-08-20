"""Shared pieces of the archive publishers (``publish_zenodo`` / ``publish_figshare``).

Everything here is archive-agnostic: locating a session's files, checking them
against the deposit manifest, building the processed bundles, reading an API
token, drawing an upload progress meter, and the citation text both deposits
share. Each publisher keeps only its own API client and metadata *shape* — the
strings live here precisely so a citation edit cannot land in one archive and
not the other.

The manifest check in particular belongs in one place. It is what stops a mirror
from quietly absorbing local pipeline artifacts, and two copies of that rule
would drift apart exactly when it matters.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import sys
import time
import zipfile
from pathlib import Path

# Import the reader's own definitions rather than re-deriving them. The cache
# layout has already changed once (get_data._migrate_flat_cache exists for that
# reason); a second copy of it here would not error on the next change, it would
# silently miss the cache and re-zip the stage dir, publishing bundles whose
# bytes differ from the primary's. Same for PROCESSED: a stage listed here but
# not there gets downloaded into raw/ as if it were an acquisition file.
# The import direction is deliberate and one-way — get_data is stdlib-only and
# participant-facing, so it must never import this module.
from get_data import CACHE, DATA_ROOT, PROCESSED, REPO_ROOT, _bundle_path, _human

STAGING = CACHE / "_publish_staging"

_CHUNK = 1 << 20  # 1 MiB

# (connect, read) for the upload PUTs. The read half only fires on a *stall*,
# so its only job is turning a silently dead socket into an exception the resume
# machinery can act on. It is sized per archive because 300s turned out to abort
# healthy-but-glacial Zenodo transfers: at ~0.15 MB/s a single socket write can
# legitimately go quiet for minutes. Generous is nearly free — the cost of a high
# value is only a later notice on a genuinely dead connection.
UPLOAD_TIMEOUT = {"figshare": (30, 300), "zenodo": (30, 1800)}

# Token files ship as templates with this marker; sending it would come back as
# a bare 401 and read like a bad token rather than an unfilled file.
PLACEHOLDER_MARKER = "PASTE_YOUR"

# --- citation text shared by every archive ---------------------------------
# The schema differs per archive (Zenodo wants related_identifiers, figshare
# wants references) but the words must not: an edit here reaches both.
TITLE_FMT = "Miniscope Workshop — Processing & Analysis: {session} session"
DESCRIPTION_HTML = (
    "<p>Example dataset for the Miniscope Workshop on processing and "
    "analysis: a miniscope recording with its behavior video and DAQ "
    "timestamps, plus every processed stage of the workshop pipeline.</p>"
    "<p>Layout: raw acquisition files (miniscope <code>*.avi</code> "
    "segments, <code>behavior.mp4</code>, neural and behavior timestamp "
    "CSVs, DAQ metadata) as individual files, and one zip per processed "
    "stage &mdash; <code>minian_out.zip</code> (Minian CNMF output), "
    "<code>deconv_out.zip</code> (calab deconvolution), and "
    "<code>eztrack_out.zip</code> (ezTrack position tracking).</p>"
    "<p>Fetched automatically by <code>scripts/get_data.py</code> in the "
    "workshop repository. This deposit mirrors the primary UCLA Dataverse "
    "copy so the workshop survives an outage at either archive.</p>"
)
KEYWORDS = ["miniscope", "calcium imaging", "place cells", "hippocampus",
            "Minian", "ezTrack", "CaMAP", "workshop", "one-photon imaging"]
REPO_URL = "https://github.com/miniscope/workshop-processing-and-analysis"


human = _human  # same formatting as the download side, by construction


def _digest(path: Path, alg: str) -> str:
    h = hashlib.new(alg)
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(_CHUNK), b""):
            h.update(chunk)
    return h.hexdigest()


_md5_cache: dict[tuple[str, int, int], str] = {}


def md5(path: Path) -> str:
    """MD5 of *path*, memoized on (path, size, mtime).

    Publishers legitimately need the same file's MD5 several times (resume
    filter, upload initiation, post-upload verify); without the cache that is
    multiple full passes over ~9 GB before the first byte goes out. The key
    invalidates itself if the file is rebuilt.
    """
    st = path.stat()
    key = (str(path), st.st_size, st.st_mtime_ns)
    if key not in _md5_cache:
        _md5_cache[key] = _digest(path, "md5")
    return _md5_cache[key]


_sha_cache: dict[tuple[str, int, int], str] = {}


def sha256(path: Path) -> str:
    """sha256 of *path*, memoized like :func:`md5`.

    The manifest check reads all ~9 GB, and a supervisor restart re-pays it
    before a single byte moves; within one process the memo makes the repeat
    free. Keyed on (path, size, mtime_ns) so a rebuilt bundle invalidates.
    """
    st = path.stat()
    key = (str(path), st.st_size, st.st_mtime_ns)
    if key not in _sha_cache:
        _sha_cache[key] = _digest(path, "sha256")
    return _sha_cache[key]


def load_token(filename: str, envvar: str, example: str | None = None) -> str:
    """Read an API token from *filename* (or *envvar*), or exit with instructions.

    Comment lines are stripped so a token file can carry its own notes, which the
    committed ``.example`` templates do. *example* names the template to copy
    when it is not simply ``<filename>.example`` (the sandbox token file shares
    the production template). Failures exit with what to fix rather than a stack
    trace — this is the first thing a maintainer hits.
    """
    if os.environ.get(envvar):
        return os.environ[envvar].strip()

    example = example or f"{filename}.example"
    path = REPO_ROOT / filename
    if not path.is_file():
        sys.exit(f"No token found.\n"
                 f"  Expected {filename} in the repo root, or ${envvar} in the environment.\n"
                 f"  Copy {example} to {filename} and paste your token in.")
    body = [ln.strip() for ln in path.read_text().splitlines()
            if ln.strip() and not ln.strip().startswith("#")]
    if not body:
        sys.exit(f"{filename} has no token in it — only comments.\n"
                 f"  Paste your token on a line of its own at the end of the file.")
    token = body[0]
    if PLACEHOLDER_MARKER in token:
        sys.exit(f"{filename} still holds the placeholder text.\n"
                 f"  Replace that line with your actual token.")
    if len(body) > 1:
        print(f"  NOTE {filename} has more than one non-comment line; using the first.")
    return token


def bundle_for(session: str, stage: str) -> Path | None:
    """The single-zipped bundle for *stage*, building it if it is not cached.

    Prefers ``data/.cache/<session>/<stage>.zip`` — the copy the archive itself
    published, so a mirror carries identical bytes. Falls back to zipping the
    extracted stage dir, which is what a maintainer who cleared the cache (or who
    never had it, because the primary archive is down) will need.

    Staged builds are session-scoped for the same reason the download cache is
    (see ``get_data._bundle_path``): every session names its bundles
    identically, and a flat staging dir would let one session's ``minian_out``
    be published under another session's DOI. And a build is atomic — written
    to a ``.part`` and renamed only on success — so an interrupted zip run can
    never be mistaken for a finished bundle and uploaded truncated.

    Note the bundles are *singly* zipped. The Dataverse deposit double-zips them
    because Dataverse silently unpacks any zip you upload; archives that store
    what you give them need no second wrapper, or readers get a zip in a zip.
    """
    cached = _bundle_path(session, stage)
    if cached.is_file():
        return cached

    stage_dir = DATA_ROOT / session / stage
    if not (stage_dir.is_dir() and any(stage_dir.iterdir())):
        return None

    built = STAGING / session / f"{stage}.zip"
    if built.is_file():
        return built
    built.parent.mkdir(parents=True, exist_ok=True)
    # Contents at the top level, no wrapping folder, so get_data.py extracts
    # straight into the stage dir.
    print(f"  building {stage}.zip from data/sessions/{session}/{stage}/ ...")
    part = built.with_suffix(".zip.part")
    with zipfile.ZipFile(part, "w", zipfile.ZIP_DEFLATED) as z:
        for item in sorted(stage_dir.rglob("*")):
            if item.is_file():
                z.write(item, item.relative_to(stage_dir).as_posix())
    os.replace(part, built)
    return built


def read_manifest(session: str) -> dict[str, tuple[int, str]] | None:
    """The deposit's own ``MANIFEST.txt`` as ``{filename: (size, sha256)}``.

    It ships *inside* ``raw/``, which makes it the authoritative list of what the
    deposit holds and — unlike asking the archive — it works offline. That
    matters here: the reason a mirror exists at all is that the primary archive
    is unreliable, so the check guarding the mirror must not depend on it.

    Covers raw files only; the processed bundles are not listed in it.
    """
    path = DATA_ROOT / session / "raw" / "MANIFEST.txt"
    if not path.is_file():
        return None
    entries: dict[str, tuple[int, str]] = {}
    for line in path.read_text().splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) >= 3:
            entries[parts[0]] = (int(parts[1]), parts[2])
    return entries or None


def collect(session: str, strict: bool = True, verify: bool = True,
            ) -> list[tuple[str, Path]]:
    """The ``(archive_name, local_path)`` pairs to upload, in the reader's layout.

    With *strict* (the default) the raw half is restricted to exactly what
    ``MANIFEST.txt`` lists. Running the pipeline writes derived videos straight
    into ``raw/`` (``minian.mp4``, ``minian_mc.mp4``), and sweeping those into a
    deposit would publish a "mirror" that mirrors nothing, hand every participant
    hundreds of MB of someone else's intermediates, and put a false
    "identical to" claim on the record. Extras are named and dropped, never
    silently included.

    *verify* re-hashes every manifest-listed file against its sha256, and it is
    independent of *strict*: choosing to include extras must not also switch off
    the check that the canonical files are intact. It reads every byte — cheap
    next to publishing bad bytes under a DOI that claims to be identical to the
    original.
    """
    raw_dir = DATA_ROOT / session / "raw"
    if not raw_dir.is_dir():
        sys.exit(f"No raw data at {raw_dir}.\n"
                 f"  Fetch the session first: python scripts/get_data.py --session {session}")

    # Skip dotfiles: .DS_Store and friends are local noise, not deposit content.
    local = {p.name: p for p in sorted(raw_dir.iterdir())
             if p.is_file() and not p.name.startswith(".")}

    manifest = read_manifest(session)
    if manifest is None:
        print("  NOTE no MANIFEST.txt — cannot tell deposit files from local "
              "artifacts (or verify them), so uploading everything in raw/.")
        items = list(local.items())
    else:
        missing = sorted(set(manifest) - set(local))
        if missing:
            sys.exit(f"raw/ is missing {len(missing)} file(s) the manifest lists: "
                     f"{', '.join(missing[:5])}\n"
                     f"  Repair it first: python scripts/get_data.py --what raw")
        extras = sorted(set(local) - set(manifest) - {"MANIFEST.txt"})
        if extras and strict:
            print(f"  excluding {len(extras)} local file(s) not in the deposit "
                  f"manifest: {', '.join(extras)}")
        elif extras:
            print(f"  INCLUDING {len(extras)} file(s) beyond the deposit manifest "
                  f"(--include-extras): {', '.join(extras)}")
        keep = [n for n in local
                if n in manifest or n == "MANIFEST.txt" or not strict]
        items = [(n, local[n]) for n in sorted(keep)]

        bad = []
        for name, path in items:
            if name not in manifest:
                continue  # extras and MANIFEST.txt itself have no entry to check
            want_size, want_sha = manifest[name]
            if path.stat().st_size != want_size:
                bad.append(f"{name}: size {path.stat().st_size} != {want_size}")
            elif verify and sha256(path) != want_sha:
                bad.append(f"{name}: sha256 mismatch")
        if bad:
            sys.exit("Local raw files do not match the manifest:\n  "
                     + "\n  ".join(bad)
                     + "\n  Repair with: python scripts/get_data.py --what raw --force")
        print(f"  {len(manifest)} manifest-listed files intact"
              f"{' (sha256 verified)' if verify else ' (sizes only)'}.")

    for stage in PROCESSED:
        bundle = bundle_for(session, stage)
        if bundle is None:
            print(f"  SKIP {stage}.zip: neither cached nor present as a stage dir.")
            continue
        items.append((f"{stage}.zip", bundle))
    return items


def add_common_args(ap: argparse.ArgumentParser) -> None:
    """The CLI surface both publishers share; each adds its own resume flag."""
    ap.add_argument("--session", default="prerecorded",
                    help="session under data/sessions/ to publish (default: prerecorded)")
    ap.add_argument("--publish", action="store_true",
                    help="publish at the end, minting the DOI. Without this the "
                         "deposit is left as an editable draft")
    ap.add_argument("--primary-doi", default="10.25346/S6SGHPCZ",
                    help="DOI of the deposit this mirrors, recorded in the metadata "
                         "(pass '' to omit)")
    ap.add_argument("--include-extras", action="store_true",
                    help="also upload local files in raw/ that the deposit manifest "
                         "does not list (pipeline artifacts like minian.mp4). Off by "
                         "default so the mirror stays a mirror; manifest-listed files "
                         "are verified either way")
    ap.add_argument("--no-verify", action="store_true",
                    help="skip re-hashing raw files against MANIFEST.txt (faster, but "
                         "publishes without checking the bytes)")
    ap.add_argument("--dry-run", action="store_true",
                    help="list what would be uploaded and exit, touching no network")


def plan(args: argparse.Namespace) -> list[tuple[str, Path]] | None:
    """Collect + print the upload plan; ``None`` means --dry-run handled it."""
    items = collect(args.session, strict=not args.include_extras,
                    verify=not args.no_verify)
    total = sum(p.stat().st_size for _, p in items)
    print(f"Session '{args.session}': {len(items)} files, {human(total)} total\n")
    for name, path in items:
        print(f"  {name:28s} {human(path.stat().st_size):>10s}")
    if args.dry_run:
        print("\n--dry-run: nothing uploaded.")
        return None
    return items


def report_resume(n_items: int, todo: list) -> None:
    """Print what the resume filter skipped and what is left to send."""
    skipped = n_items - len(todo)
    if skipped:
        print(f"  {skipped} file(s) already stored and matching — skipping.")
    if todo:
        paths = [t[1] for t in todo]
        print(f"  uploading {len(todo)} file(s), "
              f"{human(sum(p.stat().st_size for p in paths))}")


def draft_hint(script: str, session: str, url: str, flag: str, ident) -> str:
    """The "draft is ready, publish it deliberately" instructions."""
    return (f"\nDraft ready but NOT published:\n    {url}\n"
            f"Review it, then publish with:\n"
            f"    python scripts/{script} --session {session} "
            f"{flag} {ident} --publish")


def mirror_hint(session: str, new_doi: str) -> str:
    """The post-publish "add this to SESSIONS" instructions.

    Deliberately does *not* print a full list literal. It used to, with the
    primary first — which, followed verbatim while publishing a second mirror,
    would have silently dropped the first one. A helper that generates code must
    not restate an ordering policy that lives in another file.
    """
    return (f"\nNext: add this DOI to SESSIONS[{session!r}] in "
            f"scripts/get_data.py:\n"
            f'        "{new_doi or "<mirror DOI>"}",\n'
            f"  Keep the list ordered by measured download throughput, fastest\n"
            f"  first — see the comment above SESSIONS. Then fetches fail over\n"
            f"  automatically.")


class TransientArchiveError(RuntimeError):
    """A server-side failure worth retrying rather than aborting on.

    Distinct from the SystemExit that ``_raise`` produces for real API errors:
    a 400 or a 401 means the request was wrong and will stay wrong, while a 500
    from a storage host mid-upload is weather. Keeping them separate is what
    lets :func:`retrying` be aggressive without papering over genuine bugs.
    """


# 5xx is the storage layer having a bad moment; 429 is us being asked to slow
# down. Both pass with time, and both used to kill a multi-hour upload outright.
RETRYABLE_STATUS = {429, 500, 502, 503, 504}


def retrying(fn, label: str, attempts: int = 7) -> None:
    """Run *fn* with exponential backoff on transient transport failures.

    Multi-hour uploads to throttled archives fail in transient ways we have each
    seen for real: a gateway 502 mid-push, a 500 from the upload host on a
    single part, a socket write stalled by throttling, and — repeatedly —
    intermittent DNS resolution on the uploading machine.
    Every caller has real resume machinery behind it (Zenodo skips complete
    files, figshare re-reads its part list and continues mid-file), so a retry
    costs only what was genuinely lost.

    The budget is deliberately generous: ~30 minutes across the attempts, since
    the failure that actually killed a run was a DNS window wider than a
    three-minute linear backoff. Only transport-level errors retry; API errors
    (SystemExit from _raise) mean something is genuinely wrong and still abort
    immediately.
    """
    import requests

    for attempt in range(1, attempts + 1):
        try:
            fn()
            return
        except (requests.ConnectionError, requests.Timeout,
                TransientArchiveError) as exc:
            if attempt == attempts:
                raise SystemExit(
                    f"{label}: still failing after {attempts} attempts "
                    f"({type(exc).__name__}) - re-run to resume.")
            wait = min(30 * 2 ** (attempt - 1), 600)
            print(f"       {label}: {type(exc).__name__}, "
                  f"retry {attempt}/{attempts - 1} in {wait}s")
            time.sleep(wait)


def run(main) -> None:
    """Run *main*, turning a stray transient error into a readable exit.

    Control-plane calls outside an upload loop have no retry wrapper around
    them, so without this a 503 on (say) the final publish surfaces as a
    traceback rather than the "re-run to resume" every other failure gives.
    """
    try:
        sys.exit(main())
    except TransientArchiveError as exc:
        sys.exit(f"{exc}\n  Transient archive error - re-run to resume.")


class Progress:
    """File wrapper that draws a single-line progress meter as it is read.

    Upload clients stream from any object with ``read``; counting bytes on the
    way through is what keeps a 343 MB PUT from looking hung. ``len`` is defined
    so the client sets Content-Length and streams rather than buffering.

    Do NOT add ``tell``/``seek`` to this class. requests' ``super_len`` subtracts
    ``tell()`` from ``len()`` when both exist, which would silently understate
    Content-Length for every byte-range part after the first.

    *part* is an inclusive ``(start, end)`` byte range, for archives that upload
    in explicit parts; omit it to stream the whole file. *done* seeds the
    whole-file counter so a part-wise upload still shows overall progress.

    Redraws are throttled (the transport reads in ~16 KiB chunks — unthrottled,
    a 9 GB push is ~600k writes), and skipped entirely when stdout is not a tty,
    where ``\\r`` cannot overwrite and would only bloat the log.
    """

    def __init__(self, path: Path, label: str, part: tuple[int, int] | None = None,
                 done: int = 0):
        self._f = open(path, "rb")
        size = path.stat().st_size
        if part is None:
            self._remaining = size
        else:
            start, end = part  # inclusive byte range, as the archive states it
            self._f.seek(start)
            self._remaining = end - start + 1
        self._len = self._remaining
        # Whole-file counters, so a part-wise upload still shows overall progress.
        self._done = done
        self._total = size
        self._label = label
        self._tty = sys.stdout.isatty()
        self._last_draw = 0.0

    def __len__(self) -> int:
        return self._len

    def read(self, size: int = -1) -> bytes:
        if self._remaining <= 0:
            return b""
        if size is None or size < 0:
            size = self._remaining
        chunk = self._f.read(min(size, self._remaining))
        self._remaining -= len(chunk)
        self._done += len(chunk)
        now = time.monotonic()
        if self._tty and now - self._last_draw >= 0.25:
            self._last_draw = now
            pct = f"{self._done / self._total * 100:5.1f}%" if self._total else "  ?  "
            sys.stdout.write(f"\r       {self._label} {pct}  "
                             f"{human(self._done)} / {human(self._total)}      ")
            sys.stdout.flush()
        return chunk

    @property
    def done(self) -> int:
        return self._done

    def close(self) -> None:
        self._f.close()

    @staticmethod
    def clear() -> None:
        if sys.stdout.isatty():
            sys.stdout.write("\r" + " " * 79 + "\r")
            sys.stdout.flush()
