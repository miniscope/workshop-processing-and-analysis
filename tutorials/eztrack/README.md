# eztrack

Behavioral tracking: extract the animal's position from the behavior video.

- **Env:** the shared `.venv`
- **Source:** the [eztrack fork](https://github.com/daharoni/ezTrack) (`eztrack` v2.x; pure-Python, ships its notebooks)

Installed from the fork via `pip install git+https://github.com/daharoni/ezTrack`
(already in `requirements.txt`).

## Get the notebooks

`scripts/fetch_notebooks.py` copies eztrack's bundled notebooks into
`tutorials/eztrack/notebooks/`. To (re)fetch just eztrack:

```bash
eztrack notebooks list                                 # see what's available
eztrack notebooks copy --all -o tutorials/eztrack/notebooks
```

Bundled: `LocationTracking_Individual` (single video) and
`LocationTracking_BatchProcess` (many videos).

## Inputs / outputs

| | path |
|---|---|
| in | `data/sessions/<session>/raw/` (behavior video) |
| out | `data/sessions/<session>/eztrack_out/` (position CSV: `frame, x, y, detected, distance_px, ...`) |

## How this feeds the capstone

eztrack writes a **flat** CSV (`frame, x, y, ...`), but CaMAP expects a
**DeepLabCut-style** CSV (3-row scorer/bodypart/coord header). The capstone glue
`capstone/workshop_glue/eztrack_to_dlc.py` converts between them — a good
teaching moment about position-format conventions.

## TODO
- [ ] Confirm which eztrack export the example session uses (raw track vs scaled).
