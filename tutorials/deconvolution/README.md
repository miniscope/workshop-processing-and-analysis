# Deconvolution (calab: CaTune / CaDecon)

The explicit middle stage of the pipeline: deconvolve the Minian-denoised
calcium traces into a per-unit estimate of neural activity. Provided by `calab`
(`pip install calab`), which ships two tools:

- **CaTune** — interactive training/tuning web interface
- **CaDecon** — deconvolution

## Just exploring? (no data needed)

Both apps are hosted and generate their own simulated data **in the browser**,
so you can pick the simulation parameters yourself with no recording on hand:

- CaTune: https://miniscope.github.io/CaLab/CaTune/
- CaDecon: https://miniscope.github.io/CaLab/CaDecon/

`--demo` just opens those landing pages for you (no session data, no save-back —
the simulated traces live in the browser):

```bash
python tutorials/deconvolution/run_cadecon.py --demo
python tutorials/deconvolution/run_catune.py --demo
```

The save path (producing the `activity.npy` that CaMAP consumes) is the
**session** path below, which sends your real Minian traces to the app. Because
this step is explicit, **Minian's own deconvolution is skipped** (see
`tutorials/minian/`) — calab owns deconvolution here, and CaMAP's built-in OASIS
is bypassed.

- **Env:** the shared `.venv`

## Run

Two equivalent front-ends, same calab calls and same output — use whichever you
prefer:

- **Notebook** (`deconvolution.ipynb`) — the interactive companion. Both tools
  in one notebook, each with an *explore* path (open the hosted app, simulate
  in-browser, no data) and a *your-data* path (send your Minian `C` traces over
  the bridge and save `activity.npy`). Recommended for the workshop, and it keeps
  the whole pipeline in Jupyter. `tune()` returns the tuned params straight back
  to the notebook, so CaTune doesn't need the export-download-rerun dance the
  script does.
- **Scripts** (`run_cadecon.py` / `run_catune.py`) — headless front-end for
  batch/non-interactive regeneration (used by `prepare_session.py`).

calab works on a `.npy` of calcium traces and the browser apps return the
deconvolved activity. The wrapper scripts handle the session plumbing
(Minian → `.npy` → browser → `deconv_out/activity.npy`):

```bash
source .venv/bin/activate          # Windows: .venv\Scripts\Activate.ps1

# Option A — CaDecon (automated): opens the browser, then saves activity.npy
python tutorials/deconvolution/run_cadecon.py --session prerecorded --fs 20

# Option B — CaTune (interactive tuning), two phases:
python tutorials/deconvolution/run_catune.py --session prerecorded --fs 20
#   ...tune in the browser, EXPORT the params JSON, download it, then:
python tutorials/deconvolution/run_catune.py --session prerecorded \
    --params <downloaded_export.json>
```

Both write `data/sessions/<session>/deconv_out/activity.npy` (shape
`(n_cells, n_frames)`, rows aligned to the Minian `C` order).

Under the hood the scripts call the `calab` CLI (`convert -f minian` → `.npy`,
then `tune` + `deconvolve`, or `cadecon`); the notebook calls calab's Python API
(`load_minian`, `tune`, `decon`, …) directly. calab *upstream* ships **no
notebooks**, so it's not part of `fetch_notebooks.py` — `deconvolution.ipynb`
here is workshop-authored and committed (like the CaMAP capstone notebook).

## Inputs / outputs

| | path |
|---|---|
| in | `data/sessions/<session>/minian_out/C.zarr` (Minian denoised `C`) |
| out | `data/sessions/<session>/deconv_out/activity.npy` (deconvolved neural activity) |

## How this feeds the capstone

The capstone glue (`capstone/workshop_glue/deconv_inject.py`,
`inject_deconv_activity`) loads `deconv_out/activity.npy`, aligns its rows with
`ds.traces`'s unit ids (same order as the Minian `C` traces fed to calab), and
sets `ds.good_unit_ids` / `ds.S_list` directly — bypassing CaMAP's OASIS. Each
activity trace must match the neural frame count.

(If you instead deconvolve *inside* CaMAP, drop tuned OASIS params into the
analysis config's `neural.oasis` block and call `ds.deconvolve()` — but that's
not the path this workshop teaches.)
