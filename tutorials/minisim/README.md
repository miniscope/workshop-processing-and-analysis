# minisim

Simulate miniscope recordings to build intuition for the upstream signal before
any processing — and generate simulated data you can carry through the rest of
the workshop.

- **Env:** the shared `.venv`
- **Source:** [minisim](https://github.com/miniscope/minisim) (notebooks ship inside the package)

## Get the notebooks

minisim's teaching notebooks are already committed under
`tutorials/minisim/notebooks/`. `scripts/fetch_notebooks.py` optionally refreshes
them to your installed minisim. To (re)fetch just minisim:

```bash
minisim-notebooks list                                   # see what's available
minisim-notebooks copy --all -o tutorials/minisim/notebooks -f
```

Then open them:

```bash
jupyter lab    # navigate to tutorials/minisim/notebooks/
```

## What's bundled

`copy --all` writes one folder per notebook into `tutorials/minisim/notebooks/`.
Two categories ship side by side:

The teaching ladder (each notebook isolates one effect to *explain* it):
- `01_anatomy` — anatomy of a simulated recording
- `02_demixing` — source demixing
- `03_metrics` — quality metrics

Production tools (expose every knob to *make usable simulated data*):
- `build_recording` — the data generator

> minisim *generates* its recordings from code, so these notebooks need no data
> download. The `build_recording` notebook is a good way to produce a
> simulated session to practice the downstream tools on.
