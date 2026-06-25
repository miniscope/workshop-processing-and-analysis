# Workshop data

Data is organized into named **sessions**. Nothing here is committed to git (see
`.gitignore`); everything is fetched from Zenodo by `scripts/get_data.py` using
`pooch` (checksummed + cached — the same library Minian uses).

Each session is **one Zenodo deposit**, and `get_data.py` **auto-discovers** its
files and checksums straight from the DOI (`pooch.load_registry_from_doi`) — so
adding a session means setting one DOI, with no hand-listed filenames or hashes.

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

## Deposit layout (per session)

One Zenodo deposit per session holds **raw as individual files** plus **one zip
per processed stage**. `get_data.py` routes them automatically: a file named
`minian_out.zip` / `deconv_out.zip` / `eztrack_out.zip` is extracted into that
stage's dir; every other file is a raw file and lands in `raw/`. A stage that
hasn't been uploaded yet is simply skipped.

## `raw/` contents

The raw stage is published on Zenodo as individual files (not a zip) and lands in
`raw/` under these names:

```
raw/
├── behavior.mp4            # behavior camera, grayscale H.264, ~47 fps (50 nominal)
├── behavior_timestamp.csv  # behavior DAQ clock (one row per behavior.mp4 frame)
├── behavior_metaData.json
├── 0.avi ... N.avi         # miniscope, 600x600 grayscale, ~20 fps, lossless raw
├── neural_timestamp.csv    # miniscope DAQ clock (one row per miniscope frame)
└── neural_metaData.json
```

The miniscope segments keep the modern DAQ names (`0.avi`, `1.avi`, ...). Minian's
default file pattern is `msCam[0-9]+\.avi`, so point it at `raw/` with
`MINIAN_FILE_PATTERN=[0-9]+\.avi$` (the videos then load and `behavior.mp4` is
ignored). For the example session the behavior camera ran at **~47 fps**, not 20 —
set the fps accordingly in eztrack and `capstone/config/data_paths.yaml`.

## Two sessions

- **`prerecorded`** — the backup dataset, always available on Zenodo. Use this so
  the workshop runs even if a live recording doesn't happen.
- **`live`** — recorded during the workshop and uploaded to Zenodo if that works
  out. Its DOI isn't known until then, so pass it at fetch time with `--doi`
  (no code edit, no `git pull`): `--session live --doi 10.5281/zenodo.NNNNNN`.

Participants can pull **one or both** — just run the command once per session
they want.

## Download

```bash
python scripts/get_data.py                              # prerecorded, all stages
python scripts/get_data.py --what raw                   # just the raw recording (feeds Minian + eztrack)
python scripts/get_data.py --what processed             # minian_out + deconv_out + eztrack_out
python scripts/get_data.py --session live --doi 10.5281/zenodo.NNNNNN   # the workshop recording
python scripts/get_data.py --force                      # re-download even if local data exists
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
- [ ] Publish the `prerecorded` Zenodo deposit (`prepare_session.py` →
      `zenodo_publish.py`) and set its DOI in `scripts/get_data.py`
      (`SESSIONS["prerecorded"]`). Filenames + checksums are read from the DOI —
      nothing else to fill.
- [ ] Build + upload the processed bundles as `minian_out.zip`, `deconv_out.zip`,
      `eztrack_out.zip` (each zip's **contents at the top level**, no wrapping
      folder, so they extract straight into the stage dir).
- [ ] Live: after the workshop recording, `prepare_session.py` → `zenodo_publish.py`,
      then hand participants the DOI for `--session live --doi …` (or set
      `SESSIONS["live"]`).
- [ ] Smoke-test `get_data.py` against the real DOI once published (the
      `XXXXXXX` placeholder will fail discovery until then).
