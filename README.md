# Miniscope Workshop — Processing & Analysis

End-to-end curriculum for going from a raw miniscope recording to a place-cell
analysis. The workshop walks through each tool in the pipeline and then ties
them together in a capstone notebook that combines processed neural activity
with tracked behavior to find and quantify place cells.

This repo is the **hub**: it owns the agenda, the shared example dataset, the
environment, and the capstone notebook. The per-tool teaching notebooks live in
their own repos (linked below) — we pin and reference them rather than copy them.

## Pipeline at a glance

```
raw miniscope video ─▶ Minian ─▶ C / C_lp (denoised) ─▶ CaTune/CaDecon ─▶ activity ─┐
                                 A.zarr / max_proj.zarr ────────────────────────────┤
                                                                                     ├─▶ CaMAP ─▶ place cells
raw behavior video  ─▶ eztrack ─▶ position.csv ──────────────────────────────────────┘   (capstone)

minisim: simulate recordings to understand the upstream signal
Deconvolution is an explicit stage (calab) — Minian's own deconvolution is skipped.
```

## Agenda

The workshop runs in order — each step builds on the previous one — and ends
with the capstone that ties everything together. Everything shares one
environment, so a step can also be run standalone against downloaded data.

| # | Module | Consumes | Produces | Materials |
|---|--------|----------|----------|-----------|
| 1 | **minisim** — simulate recordings | (code) | simulated recording (optional) | [`tutorials/minisim/`](tutorials/minisim/) |
| 2 | **Minian** — CNMF processing | raw miniscope video | denoised traces `C`/`C_lp`, `A`, `max_proj` | [`tutorials/minian/`](tutorials/minian/) |
| 3 | **CaTune / CaDecon** — deconvolution | Minian denoised traces | deconvolved neural activity | [`tutorials/deconvolution/`](tutorials/deconvolution/) |
| 4 | **eztrack** — behavioral tracking | raw behavior video | position CSV | [`tutorials/eztrack/`](tutorials/eztrack/) |
| 5 | **CaMAP** — capstone, place cells | Minian + deconv + eztrack + timestamps | `.camap` bundle, place-cell metrics | [`capstone/`](capstone/) |

Steps 1 (minisim) and 4 (eztrack) are independent of the neural processing
chain (2→3); the capstone (5) needs the outputs of 2, 3, and 4.

## The data story

Data is organized into named **sessions** under `data/sessions/<name>/`, each
holding the raw recording and every processed stage:

```
data/sessions/<name>/
├── raw/         miniscope video, behavior video, neural + behavior timestamps
├── minian_out/  Minian output  (C/C_lp, A, max_proj)        — step 2
├── deconv_out/  calab output   (deconvolved neural activity) — step 3
└── eztrack_out/ eztrack output (position CSV)                — step 4
```

Two sessions:
- **`prerecorded`** — the backup dataset, always available from the public archive.
- **`live`** — recorded during the workshop, downloaded if that pans out.

**Raw** (videos + timestamps) feeds Minian (step 2) and eztrack (step 4).
**Processed** stages feed calab (step 3) and CaMAP (step 5) — and those inputs
can be either *your own local output* from the upstream steps **or** the
processed bundles **in the public archive** (UCLA Dataverse today; Zenodo too).
`scripts/get_data.py` resolves this **local-first**: each stage you already
produced is kept, and only the missing stages are downloaded (checksummed +
cached). So whether you ran the upstream step or not, the capstone reads the
same path.

See [`data/README.md`](data/README.md) for the download commands and layout.

## Quick start

Prerequisites: **Python 3.11–3.13**, **git**, and **ffmpeg**. Starting from a
bare machine? [INSTALL.md](INSTALL.md) walks through installing all three per OS.

```bash
git clone https://github.com/miniscope/workshop-processing-and-analysis.git
cd workshop-processing-and-analysis
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt           # see INSTALL.md for the pinned lock
# pull each tool's teaching notebooks into tutorials/<tool>/notebooks/
python scripts/fetch_notebooks.py
# fetch the workshop data (default: the prerecorded backup session, all stages)
python scripts/get_data.py
```

Each tool ships its teaching notebooks inside its package; `fetch_notebooks.py`
copies them out (version-matched to what's installed) so participants find them
right next to each module's README. They're regenerated, not committed.

Then open the module you're on under [`tutorials/`](tutorials/) or [`capstone/`](capstone/).

> ⚠️ **Performance (read before running Minian):** if a save/compute cell takes
> minutes instead of seconds, set `MINIAN_MEM_LIMIT` to match your RAM
> (roughly `0.7 x total_RAM / n_workers`, e.g. `12GB` on a 64 GB machine). The
> `4GB` default is sized for a 16 GB laptop and makes dask spill to disk
> needlessly on larger machines, which can turn a ~40 s save into ~10 min. See
> [`tutorials/minian/README.md`](tutorials/minian/README.md#-performance-size-the-dask-memory-limit-to-your-machine).

## Repo layout

```
workshop-processing-and-analysis/
├── README.md                 # this file
├── INSTALL.md                # venv setup + prerequisites (ffmpeg)
├── requirements.txt          # top-level deps (newest from PyPI)
├── requirements.lock         # full pinned freeze (verified-working set)
├── data/
│   ├── README.md             # sessions, archive bundles, local-first resolution
│   └── sessions/             # data/sessions/<name>/{raw,minian_out,deconv_out,eztrack_out}
├── scripts/
│   ├── get_data.py           # DOI fetch from Dataverse/Zenodo (per session, local-first)
│   └── fetch_notebooks.py    # copy each tool's bundled notebooks into tutorials/
├── tutorials/                # one folder per upstream tool (links + run notes)
│   ├── overview/             # processing_overview.ipynb (the pipeline end-to-end)
│   ├── minisim/
│   ├── minian/
│   ├── deconvolution/        # calab: CaTune / CaDecon
│   └── eztrack/
├── capstone/                 # the CaMAP integration notebook + glue
└── .github/workflows/smoke.yml   # runs the capstone headless on checkpoint data
```

## License

TBD — add a LICENSE file. Note that CaMAP itself is AGPL-3.0.
