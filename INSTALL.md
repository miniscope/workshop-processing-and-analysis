# Installation

This guide starts from a **fresh machine** with nothing installed. The workshop
runs in a single Python virtual environment (`venv`) — install once, use one
Jupyter kernel for every module. No conda required; everything installs from
PyPI plus the eztrack fork from GitHub.

Verified end-to-end: all five tools (minisim, Minian 2.0, CaTune/CaDecon via
calab, CaMAP, eztrack) resolve, install, and import together in one Python 3.12
venv with no conflicts.

> Pick your OS in each step below. Commands are run in a **terminal**:
> Windows → "PowerShell" (Start menu), macOS → "Terminal" (Spotlight),
> Linux → your terminal app.

---

## Step 0 — Install the prerequisites

You need three things that pip cannot install for you: **Python**, **git**, and
**ffmpeg**. (pip and `venv` come bundled with Python.)

### Python 3.11–3.13

CaMAP requires Python in this range; 3.12 is recommended.

- **Windows:** `winget install Python.Python.3.12`
  (or download from [python.org](https://www.python.org/downloads/) and **check
  "Add python.exe to PATH"** in the installer).
- **macOS:** `brew install python@3.12`
  (Homebrew from [brew.sh](https://brew.sh); or the python.org installer).
- **Linux (Debian/Ubuntu):** `sudo apt update && sudo apt install python3.12 python3.12-venv python3-pip`

Verify (open a **new** terminal so PATH refreshes):

```bash
python --version      # Windows: if this fails, use:  py --version
python -m pip --version
```

You should see `Python 3.1x.y`. On Windows, prefer the `py` launcher
(`py -3.12 ...`); if typing `python` opens the Microsoft Store, that's the
"App execution alias" — turn it off in Settings → Apps → Advanced app settings →
App execution aliases, or just use `py`.

### git

Needed to download the workshop and to install the eztrack fork.

- **Windows:** `winget install Git.Git` (or [git-scm.com](https://git-scm.com/download/win))
- **macOS:** `xcode-select --install` (or `brew install git`)
- **Linux:** `sudo apt install git`

Verify: `git --version`

### ffmpeg

System binary used for video I/O (the pip `ffmpeg-python` package only wraps it).

- **Windows:** `winget install ffmpeg` (or `choco install ffmpeg`)
- **macOS:** `brew install ffmpeg`
- **Linux:** `sudo apt install ffmpeg`

Verify: `ffmpeg -version`

---

## Step 1 — Get the workshop

```bash
git clone https://github.com/miniscope/workshop-processing-and-analysis.git
cd workshop-processing-and-analysis
```

## Step 2 — Create the environment and install

```bash
# create the virtual environment
python -m venv .venv          # Windows, if needed: py -3.12 -m venv .venv

# activate it
source .venv/bin/activate      # macOS/Linux
.venv\Scripts\Activate.ps1     # Windows PowerShell

# install everything (this is a large scientific stack — expect ~5-10 min)
python -m pip install --upgrade pip
python -m pip install -r requirements.txt          # newest from PyPI
# or, for the reproducible known-good set:
# python -m pip install -r requirements.lock
```

Your prompt should now show `(.venv)`. Re-activate (the `activate` line above) in
each new terminal.

## Step 3 — Register the kernel and fetch content

```bash
python -m ipykernel install --user --name workshop --display-name "Workshop"
python scripts/fetch_notebooks.py                  # tool notebooks -> tutorials/<tool>/notebooks/
python scripts/get_data.py                         # prerecorded session data (all stages)
```

Then launch Jupyter and pick the **Workshop** kernel:

```bash
jupyter lab
```

---

## newest vs. pinned

- `requirements.txt` — top-level packages, **unpinned** (pulls newest). Good
  during development.
- `requirements.lock` — a **full pinned freeze** of a verified-working set.
  Switch the workshop to this once development locks in, so the room is
  reproducible. The CI smoke test flags drift in the meantime.

## Verify the capstone runs

On the prerecorded session data, headless (same as CI — see `.github/workflows/smoke.yml`):

```bash
jupyter nbconvert --to notebook --execute --inplace \
  capstone/camap_placecells.ipynb
```

## Notes

- **eztrack** is a pure-Python, cross-platform package built from the
  [daharoni fork](https://github.com/daharoni/ezTrack) on install (it isn't
  published to PyPI). git is required for this; no compiler needed.
- **CaTune / CaDecon** (`calab`) launch a web interface; see
  `tutorials/deconvolution/README.md` (including a `--demo` / no-data path).
- **oasis-deconv** is optional and intentionally left out — the workshop does
  deconvolution in calab and bypasses CaMAP's built-in OASIS.
- Some teaching notebooks need a tool's notebook extras (e.g. `minisim[notebook]`);
  these are already in `requirements.txt`.
