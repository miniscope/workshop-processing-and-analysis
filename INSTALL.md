# Installation

The workshop targets a **single shared conda environment** (`workshop`) so
attendees install once and use one Jupyter kernel all week.

## Recommended path

```bash
conda env create -f environment.yml
conda activate workshop
python -m ipykernel install --user --name workshop --display-name "Workshop"
python scripts/download_data.py        # example data + golden checkpoints
```

Verify the capstone runs end-to-end on the golden checkpoints:

```bash
jupyter nbconvert --to notebook --execute --inplace \
  capstone/camap_placecells.ipynb
```

(That same command runs in CI — see `.github/workflows/smoke.yml`.)

## If the single environment won't resolve

CaMAP sets an aggressively modern floor (Python `>=3.11`, `xarray>=2025.10`,
`zarr>=2.17`, `pyarrow>=23`, `opencv>=4.13`). If pip's resolver refuses, the
most likely conflict is **Minian** (numba ↔ numpy ceilings, older zarr
expectation).

Do **not** pre-fragment. Instead, isolate only the offending tool:

```bash
# example: Minian in its own env, everything else stays shared
conda env create -f envs/minian.yml
conda activate minian   # for the Minian module only
```

The capstone only needs CaMAP, because by then every upstream tool is just
*files on disk* — so even if Minian lives in its own env, the capstone runs in
the shared `workshop` env against the checkpoints.

## Per-tool notes

- **CaTune** (`pip install calab`) launches a web interface; see
  `tutorials/catune/README.md` for how to start it and where it writes output.
- **OASIS** (CaMAP's fallback deconvolver): installed via conda-forge here to
  avoid the source build. If you must build from source you need a C compiler.
- **eztrack fork**: confirm the fork URL/ref in `environment.yml`.
