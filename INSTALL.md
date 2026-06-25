# Installation

The workshop runs in a **single Python virtual environment** (`venv`) so
attendees install once and use one Jupyter kernel for every module. No conda
required — everything installs from PyPI (plus the eztrack fork from GitHub).

Verified end-to-end: all five tools (minisim, Minian 2.0, CaTune/CaDecon via
calab, CaMAP, eztrack) resolve, install, and import together in one Python 3.12
venv with no conflicts.

## Prerequisites (not installed by pip)

- **Python 3.11–3.13** (CaMAP requires this range)
- **ffmpeg** — system binary used for video I/O (the pip `ffmpeg-python` package
  is only a wrapper around it):
  - macOS: `brew install ffmpeg`
  - Linux: `sudo apt install ffmpeg`
  - Windows: `winget install ffmpeg` (or `choco install ffmpeg`)
  - Verify with `ffmpeg -version`

## Recommended path

```bash
python -m venv .venv
# activate: macOS/Linux
source .venv/bin/activate
# activate: Windows PowerShell
.venv\Scripts\Activate.ps1

python -m pip install --upgrade pip
python -m pip install -r requirements.txt          # newest from PyPI
# or, for the reproducible known-good set:
# python -m pip install -r requirements.lock

python -m ipykernel install --user --name workshop --display-name "Workshop"
python scripts/download_data.py                    # example data + golden checkpoints
```

## newest vs. pinned

- `requirements.txt` — top-level packages, **unpinned** (pulls newest). Good
  during development.
- `requirements.lock` — a **full pinned freeze** of a verified-working set.
  Switch the workshop to this once development locks in, so the room is
  reproducible. The CI smoke test flags drift in the meantime.

## Verify the capstone runs

On the golden checkpoints, headless (same as CI — see `.github/workflows/smoke.yml`):

```bash
jupyter nbconvert --to notebook --execute --inplace \
  capstone/camap_placecells.ipynb
```

## Notes

- **eztrack** is a pure-Python, cross-platform package built from the
  [daharoni fork](https://github.com/daharoni/ezTrack) on install (it isn't
  published to PyPI). No compiler needed.
- **CaTune** (`calab`) launches a web interface; see
  `tutorials/deconvolution/README.md` for how to start it and where it writes.
- **oasis-deconv** is optional and intentionally left out — the workshop does
  deconvolution in calab and bypasses CaMAP's built-in OASIS.
