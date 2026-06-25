# eztrack

Behavioral tracking: extract the animal's position from the behavior video.

- **Env:** `workshop`
- **Materials:** the tracking notebook in the [eztrack fork](https://github.com/daharoni/ezTrack)

The `workshop` env installs the fork (`eztrack` v2.x, pip-installable, ships its
notebooks) via `pip install git+https://github.com/daharoni/ezTrack`.

## Inputs / outputs

| | path |
|---|---|
| in | `data/example_session/raw/` (behavior video) |
| out | `data/example_session/eztrack_out/` (position CSV: `frame, x, y, detected, distance_px, ...`) |

## How this feeds the capstone

eztrack writes a **flat** CSV (`frame, x, y, ...`), but CaMAP expects a
**DeepLabCut-style** CSV (3-row scorer/bodypart/coord header). The capstone glue
`capstone/workshop_glue/eztrack_to_dlc.py` converts between them — a good
teaching moment about position-format conventions.

## TODO
- [ ] Confirm which eztrack export the example session uses (raw track vs scaled).
