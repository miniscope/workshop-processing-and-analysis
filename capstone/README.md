# Capstone — CaMAP place-cell analysis

Tie it all together: bring in the denoised miniscope traces (Minian), the
deconvolved neural activity (calab: CaTune / CaDecon), and the tracked behavior
(eztrack), then walk through combining neuro-behavioral data and analyzing place
cells with full metrics.

- **Env:** the shared `.venv` (only CaMAP is needed here — upstream tools are just files now)
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

- `eztrack_to_camap.py` — converts eztrack's flat `frame,x,y` CSV into the
  DeepLabCut-style CSV CaMAP reads. **Fully implemented.**
- `deconv_inject.py` — loads `deconv_out/activity.npy` (calab CaTune/CaDecon
  output), aligns rows with `ds.traces` unit ids, and injects into
  `ds.good_unit_ids` / `ds.S_list`, bypassing CaMAP's OASIS. **Implemented.**
  (Produce `activity.npy` with `tutorials/deconvolution/run_catune.py` /
  `run_cadecon.py`.)

Both live in [`workshop_glue/`](workshop_glue/) and are imported by the notebook.

## Inputs

All under the active session, `data/sessions/<session>/` (default `prerecorded`):

| source | path |
|---|---|
| Minian | `minian_out/` |
| deconvolution | `deconv_out/` (calab: CaTune/CaDecon) |
| eztrack | `eztrack_out/` |
| timestamps | `raw/` (`neural_timestamp.csv`, `behavior_timestamp.csv`) |

These are populated either by your own upstream runs or by
`python scripts/get_data.py` (local-first — see `data/README.md`).
