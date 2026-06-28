#!/usr/bin/env python
"""Fast structural check for the repo's notebooks.

Validates that every committed .ipynb is well-formed nbformat — a cheap gate
that catches a corrupted or hand-edited notebook in seconds, without spinning
up the full scientific stack the capstone smoke test needs.

Skips fetched tutorial notebooks (tutorials/*/notebooks/), which are generated
by scripts/fetch_notebooks.py and not committed.
"""

from __future__ import annotations

import sys
from pathlib import Path

import nbformat

REPO_ROOT = Path(__file__).resolve().parent.parent
SKIP_DIRS = {".git", ".venv", "__pycache__"}


def iter_notebooks() -> list[Path]:
    notebooks = []
    for path in REPO_ROOT.rglob("*.ipynb"):
        rel_parts = set(path.relative_to(REPO_ROOT).parts)
        if rel_parts & SKIP_DIRS:
            continue
        # tutorials/<tool>/notebooks/ is fetched, not committed
        if "notebooks" in path.parts and "tutorials" in path.parts:
            continue
        notebooks.append(path)
    return sorted(notebooks)


def main() -> int:
    notebooks = iter_notebooks()
    if not notebooks:
        print("No notebooks found to validate.")
        return 0

    failures = []
    for path in notebooks:
        rel = path.relative_to(REPO_ROOT)
        try:
            nbformat.validate(nbformat.read(path, as_version=4))
            print(f"OK   {rel}")
        except Exception as exc:  # nbformat.ValidationError, JSON errors, etc.
            print(f"FAIL {rel}: {exc}")
            failures.append(rel)

    if failures:
        print(f"\n{len(failures)} invalid notebook(s): " + ", ".join(map(str, failures)))
        return 1
    print(f"\nAll {len(notebooks)} notebook(s) valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
