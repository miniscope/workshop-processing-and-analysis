# Deconvolution (calab: CaTune / CaDecon)

The explicit middle stage of the pipeline: deconvolve the Minian-denoised
calcium traces into a per-unit estimate of neural activity. Provided by `calab`
(`pip install calab`), which ships two tools:

- **CaTune** — interactive training/tuning web interface
- **CaDecon** — deconvolution

Either produces the deconvolved output that CaMAP consumes. Because this step is
explicit, **Minian's own deconvolution is skipped** (see `tutorials/minian/`) —
calab owns deconvolution here, and CaMAP's built-in OASIS is bypassed.

- **Env:** the shared `.venv`

## Run

```bash
source .venv/bin/activate          # Windows: .venv\Scripts\Activate.ps1
# launch CaTune / run CaDecon from calab
# TODO: confirm the exact launch command(s) from `calab`
```

## Inputs / outputs

| | path |
|---|---|
| in | `data/example_session/minian_out/` (Minian denoised traces `C` / `C_lp`) |
| out | `data/example_session/deconv_out/` (deconvolved neural activity) |

## How this feeds the capstone

The capstone glue (`capstone/workshop_glue/deconv_inject.py`,
`inject_deconv_activity`) loads the deconvolved neural activity and sets
`ds.good_unit_ids` / `ds.S_list` directly, bypassing CaMAP's OASIS. Each
activity trace must match the neural frame count.

(If you instead deconvolve *inside* CaMAP, drop tuned OASIS params into the
analysis config's `neural.oasis` block and call `ds.deconvolve()` — but that's
not the path this workshop teaches.)

## TODO
- [ ] Confirm the `calab` launch command(s) + where CaTune/CaDecon write output.
- [ ] Document the exact output format so `deconv_inject.py` can parse it.
