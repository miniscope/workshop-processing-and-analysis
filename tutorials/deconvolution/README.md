# Deconvolution (calab: CaTune / CaDecon)

The explicit middle stage of the pipeline: deconvolve the Minian-denoised
calcium traces into a per-unit estimate of neural activity. Provided by `calab`
(`pip install calab`), which ships two tools:

- **CaTune** — interactive training/tuning web interface
- **CaDecon** — deconvolution

## Just exploring? (no data needed)

Both apps are hosted and can generate their own simulated data in-browser — open
them directly for a zero-setup look:

- CaTune: https://miniscope.github.io/CaLab/CaTune/
- CaDecon: https://miniscope.github.io/CaLab/CaDecon/

Or launch from Python with synthetic traces (uses `calab.simulate()`, so no
recording is required) — this also keeps the save path working:

```bash
python tutorials/deconvolution/run_cadecon.py --demo
python tutorials/deconvolution/run_catune.py --demo
```

Either produces the deconvolved output that CaMAP consumes. Because this step is
explicit, **Minian's own deconvolution is skipped** (see `tutorials/minian/`) —
calab owns deconvolution here, and CaMAP's built-in OASIS is bypassed.

- **Env:** the shared `.venv`

## Run

calab works on a `.npy` of calcium traces and the browser apps return the
deconvolved activity. Two thin wrapper scripts handle the session plumbing
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

Under the hood they call the `calab` CLI: `convert -f minian` (→ `.npy`),
then `tune` + `deconvolve`, or `cadecon`. calab ships **no notebooks** (web UI /
CLI), so it's not part of `fetch_notebooks.py`.

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

## TODO
- [ ] Confirm `--fs` and the `C` vs `C_lp` trace name for the example session.
- [ ] Confirm CaDecon's row order matches Minian `C` (the inject asserts this).
