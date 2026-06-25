# Minian

CNMF processing of the raw miniscope video into calcium traces and spatial
footprints.

**Deconvolution is skipped here.** In `update_temporal` we keep the denoised
calcium (`C` / `C_lp`) but do not use Minian's deconvolved-activity estimate
(`S`) — the explicit deconvolution stage (calab: CaTune / CaDecon) owns that
downstream. So Minian's output for this workshop is denoised traces +
footprints, not deconvolved activity.

- **Env:** `workshop` (fallback `envs/minian.yml` if the shared env can't resolve — see INSTALL.md)
- **Materials:** the [Minian walkthrough notebook](https://github.com/denisecailab/minian) <!-- TODO: confirm URL + pin ref -->

## Inputs / outputs

| | path |
|---|---|
| in | `data/example_session/raw/` (miniscope video) |
| out | `data/example_session/minian_out/` → `C.zarr` (and/or `C_lp.zarr`), `A.zarr`, `max_proj.zarr` |

These zarr stores are exactly what CaMAP reads in the capstone (dims `(unit_id, frame)`).
The denoised `C` / `C_lp` traces also feed the deconvolution stage.

## TODO
- [ ] Link the exact walkthrough notebook + pin ref.
- [ ] Confirm output names match what CaMAP expects (`C.zarr` / `A.zarr` / `max_proj.zarr`).
- [ ] Ensure `A.zarr` has valid unique `unit_id` coords (CaMAP disables the footprint overlay otherwise).
