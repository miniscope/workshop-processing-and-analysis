"""Fetch workshop data from Zenodo with pooch — per session, per stage, local-first.

Data lives under ``data/sessions/<name>/`` with one subdir per stage::

    raw/         miniscope video, behavior video, neural + behavior timestamps
    minian_out/  Minian output   (step 2)
    deconv_out/  calab output    (step 3)
    eztrack_out/ eztrack output  (step 4)

Each stage is a separate Zenodo zip so it can be pulled independently. The fetch
is **local-first**: a stage you already produced (by running the upstream step)
is kept, and only the missing stages are downloaded. So whether or not you ran
Minian / calab / eztrack yourself, the capstone reads the same paths.

Downloads use ``pooch`` (checksummed + cached, the same library Minian uses), so
re-runs are free and corrupt downloads are caught.

Examples
--------
    python scripts/get_data.py                          # prerecorded, all stages
    python scripts/get_data.py --what raw               # just the raw recording
    python scripts/get_data.py --what processed         # minian+deconv+eztrack outputs
    python scripts/get_data.py --session live           # the workshop recording
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

STAGE_KEYS = ["raw", "minian_out", "deconv_out", "eztrack_out"]
GROUPS = {
    "raw": ["raw"],
    "processed": ["minian_out", "deconv_out", "eztrack_out"],
    "all": STAGE_KEYS,
}

# TODO: fill in the Zenodo DOI and per-stage sha256 hashes once data is uploaded.
# Each stage bundle is a zip of that stage's *contents* (no top-level folder), so
# it extracts directly into data/sessions/<name>/<stage>/.
SESSIONS: dict[str, dict] = {
    "prerecorded": {
        "doi": "10.5281/zenodo.XXXXXXX",  # TODO: backup dataset DOI
        "stages": {
            "raw": {"zip": "raw.zip", "hash": None},  # TODO: "sha256:..."
            "minian_out": {"zip": "minian_out.zip", "hash": None},
            "deconv_out": {"zip": "deconv_out.zip", "hash": None},
            "eztrack_out": {"zip": "eztrack_out.zip", "hash": None},
        },
    },
    "live": {
        # Set during the workshop if a freshly recorded dataset is uploaded.
        "doi": None,  # TODO
        "stages": {},
    },
}


def _nonempty(d: Path) -> bool:
    return d.is_dir() and any(d.iterdir())


def fetch_stage(session: str, stage: str, force: bool) -> bool:
    """Ensure one stage is available locally. Returns True if present afterward."""
    cfg = SESSIONS[session]
    dest = DATA_ROOT / session / stage

    if _nonempty(dest) and not force:
        print(f"  KEEP {session}/{stage}: local data present (use --force to re-download).")
        return True

    if cfg.get("doi") is None or stage not in cfg.get("stages", {}):
        print(f"  SKIP {session}/{stage}: no Zenodo bundle configured yet (TODO).")
        return False

    spec = cfg["stages"][stage]
    print(f"  GET  {session}/{stage}: {spec['zip']}")
    try:
        archive = pooch.retrieve(
            url=f"doi:{cfg['doi']}/{spec['zip']}",
            known_hash=spec["hash"],
            fname=spec["zip"],
            path=CACHE,
        )
        dest.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(archive) as z:
            z.extractall(dest)
    except Exception as exc:  # network / bad DOI / bad hash / corrupt zip
        print(f"  FAIL {session}/{stage}: {type(exc).__name__}: {exc}")
        return False
    print(f"       extracted -> data/sessions/{session}/{stage}/")
    return True


def main() -> int:
    ap = argparse.ArgumentParser(description="Fetch workshop data from Zenodo (local-first).")
    ap.add_argument("--session", default="prerecorded", choices=list(SESSIONS))
    ap.add_argument("--what", default="all", choices=list(GROUPS))
    ap.add_argument("--force", action="store_true", help="re-download even if local data exists")
    args = ap.parse_args()

    stages = GROUPS[args.what]
    print(f"Fetching session '{args.session}' ({args.what}: {', '.join(stages)}) ...")
    ok = sum(fetch_stage(args.session, s, args.force) for s in stages)
    print(f"\n{ok}/{len(stages)} stage(s) available under data/sessions/{args.session}/")
    return 0 if ok == len(stages) else 1


if __name__ == "__main__":
    sys.exit(main())
