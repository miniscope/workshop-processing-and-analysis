# CaTune

Deconvolution of the Minian-processed traces, via the CaTune training web
interface (`pip install calab`).

- **Env:** `workshop`
- **Materials:** the CaTune web interface

## Run

```bash
conda activate workshop
# launch the CaTune web interface
# TODO: confirm the exact launch command from `calab`
```

## Inputs / outputs

| | path |
|---|---|
| in | `data/example_session/minian_out/` (Minian traces) |
| out | `data/example_session/catune_out/` (deconvolved spikes and/or tuned OASIS params) |

## How this feeds the capstone

CaMAP can consume CaTune either way:

- **Deconvolved spikes** → injected directly into `ds.good_unit_ids` / `ds.S_list`,
  bypassing CaMAP's own OASIS (each spike train must match the neural frame count).
- **Tuned OASIS params** (`g`, `baseline`, `penalty`, `s_min`) → dropped into the
  CaMAP analysis config's `neural.oasis` block; CaMAP runs OASIS itself.

The capstone glue (`capstone/workshop_glue/catune_inject.py`) handles the
spikes path. Pin against the CaMAP CaTune-integration dev branch.

## TODO
- [ ] Confirm the `calab` launch command + where it writes output.
- [ ] Document the exact output format (spikes vs params) so the glue can parse it.
