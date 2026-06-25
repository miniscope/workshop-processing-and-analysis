# Workshop data

Data is organized into named **sessions**. Nothing here is committed to git (see
`.gitignore`); everything is fetched from Zenodo by `scripts/get_data.py` using
`pooch` (checksummed + cached — the same library Minian uses).

## Layout

```
data/
├── sessions/
│   ├── prerecorded/          # backup dataset (always on Zenodo)
│   │   ├── raw/              # miniscope video, behavior video, neural + behavior timestamps
│   │   ├── minian_out/       # Minian output   (C/C_lp, A, max_proj)        — step 2
│   │   ├── deconv_out/       # calab output    (deconvolved neural activity) — step 3
│   │   └── eztrack_out/      # eztrack output  (position CSV)                — step 4
│   └── live/                 # recorded during the workshop, if it pans out
└── .cache/                   # pooch download cache (zips)
```

## Two sessions

- **`prerecorded`** — the backup dataset, always available on Zenodo. Use this so
  the workshop runs even if a live recording doesn't happen.
- **`live`** — recorded during the workshop and uploaded to Zenodo if that works
  out. Select it with `--session live`.

## Download

```bash
python scripts/get_data.py                     # prerecorded, all stages
python scripts/get_data.py --what raw          # just the raw recording (feeds Minian + eztrack)
python scripts/get_data.py --what processed    # minian_out + deconv_out + eztrack_out
python scripts/get_data.py --session live      # the workshop recording
python scripts/get_data.py --force             # re-download even if local data exists
```

## Local-first resolution

Each stage is a separate Zenodo bundle, fetched **local-first**:

- **Raw** (videos + timestamps) is the input to Minian (step 2) and eztrack (step 4).
- **Processed** stages (`minian_out`, `deconv_out`, `eztrack_out`) feed calab
  (step 3) and the CaMAP capstone (step 5). Their inputs can be either *your own
  local output* from running the upstream step **or** the processed bundle on
  Zenodo.

`get_data.py` keeps any stage you already produced and downloads only the missing
ones. So a participant who ran Minian uses their own `minian_out/`, while someone
who skipped it pulls the Zenodo copy — both land at the same path, and the
capstone doesn't care which.

## Timestamps

`raw/` includes the **Miniscope DAQ** timestamp CSVs (`neural_timestamp.csv`,
`behavior_timestamp.csv`) — not produced by Minian or eztrack. CaMAP's
`match_events()` needs them to align behavior onto the neural clock, and the
neural timestamp file must have the same frame count as Minian's `C.zarr`.

## TODO before the workshop
- [ ] Upload `prerecorded` raw + processed bundles to Zenodo; fill DOI + sha256
      hashes in `scripts/get_data.py`.
- [ ] Reserve/record the `live` session DOI and wire it in if recording happens.
- [ ] Confirm bundle zips contain each stage's contents at the top level (no
      wrapping folder), so they extract directly into the stage dir.
