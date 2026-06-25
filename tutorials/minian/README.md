# Minian

CNMF processing of the raw miniscope video into calcium traces and spatial
footprints.

**Deconvolution is skipped here.** Minian's `update_temporal` jointly denoises
the calcium trace `C` *and* deconvolves spikes `S` by solving a cvxpy problem
whose regularizer **is** an AR(p) model (`S = G·C`) — the AR model is the
deconvolution, so there's no way to keep `C` and turn deconvolution off. For
this workshop we replace that solve with a simple **low-pass filter** of the
extracted fluorescence `YrA` (enough denoising for the pipeline to run, no AR,
no `S`). The explicit deconvolution stage (calab: CaTune / CaDecon) owns
deconvolution downstream.

Minian's output for this workshop is therefore:
- **`C`** — the raw extracted fluorescence `YrA` (never deconvolved) — the trace
  calab consumes.
- **`C_lp`** — a low-pass-denoised copy, for display / QC.
- **`A`**, **`max_proj`** — footprints + projection, as usual.

## Workshop pipeline notebook

`pipeline_no_deconv.ipynb` (committed here) is the walkthrough: Minian's standard
`pipeline.ipynb` with the temporal-update deconvolution swapped for the low-pass
step described above, the `CNMFViewer` curation replaced by static overview
plots, and `C := YrA` at save time. Run it, then hand `minian_out/` to the
deconvolution step (`tutorials/deconvolution/run_cadecon.py`). It's a prototype
of an `update_temporal(..., deconvolve=False)` option for Minian proper.

- **Env:** the shared `.venv` (Minian 2.0 coexists with the other tools — verified)
- **Source:** [Minian](https://github.com/denisecailab/minian) (stock notebooks ship inside the package; this variant is generated from the bundled `pipeline.ipynb`)

## Get the notebooks

`scripts/fetch_notebooks.py` copies Minian's bundled notebooks into
`tutorials/minian/notebooks/`. To (re)fetch just Minian:

```bash
minian notebooks list                                  # see what's available
minian notebooks copy --all -o tutorials/minian/notebooks
```

`--all` pulls whatever the installed Minian ships — no fixed list. The released
`minian 2.0.0` bundles the **pipeline** and **cross-registration** notebooks; a
**groundtruth pipeline** notebook is picked up automatically once it's in the
installed version.

Minian also provides demo datasets via `minian data` — but this workshop uses
its own example session (see `data/README.md`).

## Inputs / outputs

| | path |
|---|---|
| in | `data/sessions/<session>/raw/` (miniscope video) |
| out | `data/sessions/<session>/minian_out/` → `C.zarr` (= raw `YrA`), `C_lp.zarr` (low-pass), `A.zarr`, `max_proj.zarr` |

These zarr stores are exactly what CaMAP reads in the capstone (dims `(unit_id, frame)`).
`C.zarr` (the un-deconvolved `YrA`) is what the deconvolution stage consumes.

## TODO
- [ ] Confirm `C.zarr` dim order / coords load cleanly in CaMAP and calab on real data.
- [ ] Ensure `A.zarr` has valid unique `unit_id` coords (CaMAP disables the footprint overlay otherwise).
- [ ] Point `dpath` at the workshop session's raw video (defaults to Minian's bundled demo).
