# Workshop data

One canonical example session flows through the whole workshop. Nothing here is
committed to git (see `.gitignore`); everything is fetched by
`scripts/download_data.py`.

## Download

```bash
python scripts/download_data.py
```

This populates:

```
data/
├── example_session/
│   ├── raw/                  # raw miniscope + behavior video
│   ├── minian_out/           # C/C_lp, A.zarr, max_proj.zarr        (Minian output)
│   ├── deconv_out/           # deconvolved spikes                    (calab: CaTune/CaDecon)
│   ├── eztrack_out/          # behavior position CSV                 (eztrack output)
│   └── timestamps/           # neural + behavior timeStamps.csv (from the DAQ)
└── checkpoints/              # GOLDEN copies of each stage above
```

## Why golden checkpoints

Each module writes into `example_session/`. The `checkpoints/` tree holds a
known-good copy of every stage's output. If an attendee's Minian run fails, they
can still do the later modules by pointing at the checkpoint instead of their
own output. The capstone reads files, so it never cares which source produced
them.

## Timestamps (important)

`timestamps/` comes from the **Miniscope DAQ** (`timeStamps.csv` for the scope
and behavior cameras) — not from Minian or eztrack. CaMAP's `match_events()`
needs them to align behavior onto the neural clock, and the neural timestamp
file must have the same frame count as Minian's `C.zarr` (trim if Minian
cropped frames).

## TODO before the workshop

- [ ] Upload the example session + checkpoints to hosting (OSF / Zenodo / GIN / S3).
- [ ] Fill in URLs + checksums in `scripts/download_data.py`.
- [ ] Add a small `--subset` sample that runs offline in seconds.
