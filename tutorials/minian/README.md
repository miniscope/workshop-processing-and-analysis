# Minian

CNMF processing of the raw miniscope video into calcium traces and spatial
footprints.

**Deconvolution is skipped here.** In `update_temporal` we keep the denoised
calcium (`C` / `C_lp`) but do not use Minian's deconvolved-activity estimate
(`S`) — the explicit deconvolution stage (calab: CaTune / CaDecon) owns that
downstream. So Minian's output for this workshop is denoised traces +
footprints, not deconvolved activity.

- **Env:** the shared `.venv` (Minian 2.0 coexists with the other tools — verified)
- **Source:** [Minian](https://github.com/denisecailab/minian) (notebooks ship inside the package)

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
| out | `data/sessions/<session>/minian_out/` → `C.zarr` (and/or `C_lp.zarr`), `A.zarr`, `max_proj.zarr` |

These zarr stores are exactly what CaMAP reads in the capstone (dims `(unit_id, frame)`).
The denoised `C` / `C_lp` traces also feed the deconvolution stage.

## TODO
- [ ] Confirm which bundled notebook is the workshop walkthrough (pipeline vs groundtruth pipeline).
- [ ] Confirm output names match what CaMAP expects (`C.zarr` / `A.zarr` / `max_proj.zarr`).
- [ ] Ensure `A.zarr` has valid unique `unit_id` coords (CaMAP disables the footprint overlay otherwise).
