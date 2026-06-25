# Minian

CNMF processing of the raw miniscope video into calcium traces and spatial
footprints.

- **Env:** `workshop` (fallback `envs/minian.yml` if the shared env can't resolve — see INSTALL.md)
- **Materials:** the [Minian walkthrough notebook](https://github.com/denisecailab/minian) <!-- TODO: confirm URL + pin ref -->

## Inputs / outputs

| | path |
|---|---|
| in | `data/example_session/raw/` (miniscope video) |
| out | `data/example_session/minian_out/` → `C.zarr`, `A.zarr`, `max_proj.zarr` |

These zarr stores are exactly what CaMAP reads in the capstone (dims `(unit_id, frame)`).

## TODO
- [ ] Link the exact walkthrough notebook + pin ref.
- [ ] Confirm output names match what CaMAP expects (`C.zarr` / `A.zarr` / `max_proj.zarr`).
- [ ] Ensure `A.zarr` has valid unique `unit_id` coords (CaMAP disables the footprint overlay otherwise).
