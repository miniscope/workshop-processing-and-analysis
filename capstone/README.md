# Capstone — CaMAP place-cell analysis

Tie it all together: bring in the denoised miniscope traces (Minian), the
deconvolved neural activity (calab: CaTune / CaDecon), and the tracked behavior
(eztrack), then walk through combining neuro-behavioral data and analyzing place
cells with full metrics.

- **Env:** `workshop` (only CaMAP is needed here — upstream tools are just files now)
- **Notebook:** [`camap_placecells.ipynb`](camap_placecells.ipynb)
- **Run last:** consumes the outputs of all four upstream modules.

## What it does

Runs CaMAP's pipeline **live**, pausing at each step to inspect the intermediate
artifact and explain it:

`load → preprocess_behavior → (inject deconvolved activity) → match_events → compute_occupancy → analyze_units → save_bundle`

Unlike CaMAP's own `view_results_arena.ipynb` (which only *views* a finished
bundle), this notebook builds the result from raw upstream outputs. Deconvolution
happened upstream (calab), so CaMAP's built-in OASIS is bypassed.

## Glue (`workshop_glue/`)

- `eztrack_to_dlc.py` — converts eztrack's flat `frame,x,y` CSV into the
  DeepLabCut-style CSV CaMAP reads. **Fully implemented.**
- `deconv_inject.py` — injects calab's (CaTune/CaDecon) deconvolved neural
  activity into `ds.good_unit_ids` / `ds.S_list`, bypassing CaMAP's OASIS.
  Injection mechanics are wired; the **output parser is a TODO** pending the
  calab dev branch.

Both live in [`workshop_glue/`](workshop_glue/) and are imported by the notebook.

## Inputs

| source | path |
|---|---|
| Minian | `data/example_session/minian_out/` (or `data/checkpoints/minian_out/`) |
| deconvolution | `data/example_session/deconv_out/` (calab: CaTune/CaDecon) |
| eztrack | `data/example_session/eztrack_out/` |
| timestamps | `data/example_session/timestamps/` |

Point at `checkpoints/` if your own upstream runs didn't complete.

## TODO
- [ ] Fill real paths once the example data is uploaded.
- [ ] Finish `deconv_inject.py` parser against the calab dev-branch output format.
- [ ] Verify the arena config (`config/`) matches the example session (fps, arena bounds, mm scale).
