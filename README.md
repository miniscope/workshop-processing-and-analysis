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
  This is what `get_data.py` fetches by default, so the workshop runs start to
  finish even without a live recording.
- **`live`** — recorded during the workshop and published partway through. The
  organizer hands you a DOI (or asks you to `git pull`) on day 2 — see
  [Getting the live recording](data/README.md#getting-the-live-recording-day-2).

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
python -m pip install -r requirements.lock          # pinned, reproducible (see INSTALL.md)
python -m ipykernel install --user --name workshop --display-name "Workshop"
python scripts/get_data.py                          # prerecorded backup session (all stages)
python scripts/verify.py                            # confirm the install before the workshop
```

Run `python scripts/verify.py` and aim for an all-`PASS` result **before the
workshop** — see [INSTALL.md](INSTALL.md) for the full step-by-step.

The workshop's **own** recording (the `live` session) is published mid-workshop;
grab it on day 2 with the one-line command in
[Getting the live recording](data/README.md#getting-the-live-recording-day-2).

Each tool's teaching notebooks are **committed** under `tutorials/<tool>/notebooks/`,
so they're there on clone. `python scripts/fetch_notebooks.py` is an optional,
non-destructive refresh that re-pulls them version-matched to your installed
tools (see each folder's `PROVENANCE.md`).

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
├── ORGANIZER.md              # organizer-only prep checklist (not for participants)
├── requirements.lock         # full pinned freeze (verified-working set) — use this
├── requirements.txt          # top-level deps (newest from PyPI) — maintainers/fallback
├── data/
│   ├── README.md             # sessions, archive bundles, local-first resolution
│   └── sessions/             # data/sessions/<name>/{raw,minian_out,deconv_out,eztrack_out}
├── scripts/
│   ├── get_data.py           # DOI fetch from Dataverse/Zenodo (per session, local-first)
│   ├── fetch_notebooks.py    # optional refresh of the committed per-tool notebooks
│   └── verify.py             # pre-flight self-check (run before the workshop)
├── tutorials/                # one folder per upstream tool (committed teaching notebooks)
│   ├── overview/             # processing_overview.ipynb (the pipeline end-to-end)
│   ├── minisim/
│   ├── minian/
│   ├── deconvolution/        # calab: CaTune / CaDecon
│   └── eztrack/
├── capstone/                 # the CaMAP integration notebook + glue
└── .github/workflows/smoke.yml   # runs the capstone headless on checkpoint data
```

## License

Copyright (c) 2026 Aharoni Lab. Licensed under **AGPL-3.0** — see [LICENSE](LICENSE).

This matches CaMAP (also AGPL-3.0) and is compatible with the other tools in the
pipeline: minian, minisim, and eztrack are GPL-3.0-or-later (GPLv3 and AGPLv3 are
explicitly combinable), and calab is MIT (permissive). AGPL-3.0 is the most
restrictive of the set, so it's the safe umbrella for the combined workshop.
