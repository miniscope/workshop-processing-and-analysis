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
raw miniscope video ─▶ Minian ─▶ C / C_lp (denoised) ─▶ CaTune/CaDecon ─▶ spikes ─┐
                                 A.zarr / max_proj.zarr ──────────────────────────┤
                                                                                   ├─▶ CaMAP ─▶ place cells
raw behavior video  ─▶ eztrack ─▶ position.csv ────────────────────────────────────┘   (capstone)

minisim: simulate recordings to understand the upstream signal
Deconvolution is an explicit stage (calab) — Minian's own deconvolution is skipped.
```

## Modules

| Tool | What it does | Materials |
|------|--------------|-----------|
| **minisim** | simulate miniscope recordings | [`tutorials/minisim/`](tutorials/minisim/) — notebooks (linked) |
| **Minian** | CNMF processing → denoised traces & footprints (deconv skipped) | [`tutorials/minian/`](tutorials/minian/) — walkthrough (linked) |
| **CaTune / CaDecon** (`pip install calab`) | explicit deconvolution stage | [`tutorials/deconvolution/`](tutorials/deconvolution/) |
| **eztrack** (fork) | behavioral tracking | [`tutorials/eztrack/`](tutorials/eztrack/) — notebook (linked) |
| **CaMAP capstone** | combine neuro + behavior, place cells | [`capstone/`](capstone/) |

The modules build on each other (simulate → process → deconvolve → track →
combine), but everything shares one environment, so order is flexible. See each
module's README for which notebook to run and what it produces.

## The data story

One canonical example session flows through every day. Each stage writes its
output into a shared `data/` tree, and we ship **golden checkpoints** of every
intermediate. So the capstone — and any attendee whose earlier run broke —
can always start from known-good inputs. The capstone reads *files*, so it
doesn't care whether they came from your own run or the golden copy.

See [`data/README.md`](data/README.md) for download links and layout.

## Quick start

```bash
git clone https://github.com/miniscope/workshop-processing-and-analysis.git
cd workshop-processing-and-analysis
# create the environment (see INSTALL.md for details / fallbacks)
conda env create -f environment.yml
conda activate workshop
# fetch the example data + golden checkpoints
python scripts/download_data.py
```

Then open the module you're on under [`tutorials/`](tutorials/) or [`capstone/`](capstone/).

## Repo layout

```
workshop-processing-and-analysis/
├── README.md                 # this file
├── INSTALL.md                # environment setup + per-tool fallbacks
├── environment.yml           # single shared env (pinned)
├── envs/                     # escape hatch: per-tool envs IF the single env can't resolve
├── data/
│   ├── README.md             # download links + checksums
│   └── checkpoints/          # golden intermediate outputs (one per stage)
├── scripts/download_data.py
├── tutorials/                # one folder per upstream tool (links + run notes)
│   ├── minisim/
│   ├── minian/
│   ├── deconvolution/        # calab: CaTune / CaDecon
│   └── eztrack/
├── capstone/                 # the CaMAP integration notebook + glue
└── .github/workflows/smoke.yml   # runs the capstone headless on checkpoint data
```

## License

TBD — add a LICENSE file. Note that CaMAP itself is AGPL-3.0.
