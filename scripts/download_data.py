"""Fetch the workshop example session and golden checkpoints.

Idempotent: skips files that already exist with a matching checksum. Fill in
the URLS table below once the data is uploaded to hosting.
"""

from __future__ import annotations

import hashlib
import sys
import urllib.request
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# name -> (url, sha256). TODO: populate after uploading to OSF/Zenodo/GIN/S3.
URLS: dict[str, tuple[str, str]] = {
    # "example_session.zip": ("https://.../example_session.zip", "<sha256>"),
    # "checkpoints.zip":     ("https://.../checkpoints.zip",     "<sha256>"),
}


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch(name: str, url: str, sha256: str) -> None:
    dest = DATA_DIR / name
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and _sha256(dest) == sha256:
        print(f"✓ {name} (cached)")
        return
    print(f"↓ {name} ...")
    urllib.request.urlretrieve(url, dest)
    got = _sha256(dest)
    if got != sha256:
        dest.unlink(missing_ok=True)
        raise SystemExit(f"checksum mismatch for {name}: expected {sha256}, got {got}")
    print(f"✓ {name}")


def main() -> int:
    if not URLS:
        print(
            "No download URLs configured yet.\n"
            "Edit scripts/download_data.py and fill in the URLS table once the "
            "example data + checkpoints are uploaded."
        )
        return 1
    for name, (url, sha256) in URLS.items():
        fetch(name, url, sha256)
    print("\nDone. Unzip archives into data/ as described in data/README.md.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
