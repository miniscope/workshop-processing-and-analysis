# Processing overview

`processing_overview.ipynb` tells the **signal's journey** across the pipeline
for one session, end to end:

```
raw fluorescence (YrA = C)  ─►  low-pass denoise (C_lp)  ─►  deconvolved neural activity
        Minian                       Minian                      calab (CaTune / CaDecon)
```

It's the *signal* counterpart to the capstone (which tells the *behavioral*
story — place cells). Footprints + field of view, a few example cells through
all three stages, and the population activity raster.

## Inputs

| | path |
|---|---|
| Minian | `data/sessions/<session>/minian_out/` → `C` (= raw `YrA`), `C_lp`, `A`, `max_proj` |
| calab  | `data/sessions/<session>/deconv_out/activity.npy` |

Produce these with `tutorials/minian/pipeline_no_deconv.ipynb` then
`tutorials/deconvolution/run_cadecon.py` (or `run_catune.py`), or fetch them with
`python scripts/get_data.py --session <session>`.

Set `SESSION` and `NEURAL_FPS` in the first code cell (defaults: `prerecorded`,
`20.0` Hz). Each stage degrades gracefully if its output is missing.
