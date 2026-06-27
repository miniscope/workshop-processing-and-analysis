# Workshop data

Data is organized into named **sessions**. Nothing here is committed to git (see
`.gitignore`); everything is fetched from a public archive by
`scripts/get_data.py` (checksummed + cached).

Each session is **one DOI-referenced deposit** (UCLA Dataverse today; Zenodo is
equally supported), and `get_data.py` **auto-discovers** its files and checksums
straight from the DOI — so adding a session means setting one DOI, with no
hand-listed filenames or hashes. Dataverse is read via its native API (pooch's
DOI resolver mishandles Dataverse's landing-page redirect); Zenodo and friends
go through pooch.

## Layout

```
data/
├── sessions/
│   ├── prerecorded/          # backup dataset (always in the archive)
│   │   ├── raw/              # miniscope video, behavior video, neural + behavior timestamps
│   │   ├── minian_out/       # Minian output   (C/C_lp, A, max_proj)        — step 2
│   │   ├── deconv_out/       # calab output    (deconvolved neural activity) — step 3
│   │   └── eztrack_out/      # eztrack output  (position CSV)                — step 4
│   └── live/                 # recorded during the workshop, if it pans out
└── .cache/                   # download cache (zips)
```

## Deposit layout (per session)

One deposit per session holds **raw as individual files** plus **one zip
per processed stage**. `get_data.py` routes them automatically: a file named
`minian_out.zip` / `deconv_out.zip` / `eztrack_out.zip` is extracted into that
stage's dir; every other file is a raw file and lands in `raw/`. A stage that
hasn't been uploaded yet is simply skipped.

## `raw/` contents

The raw stage is published as individual files (not a zip) and lands in
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

The miniscope segments keep the modern DAQ names (`0.avi`, `1.avi`, ...). The
workshop Minian notebook defaults `dpath` to this `raw/` dir and uses the file
pattern `[0-9]+\.avi$` out of the box, so the `.avi` segments load and
`behavior.mp4` is ignored (override with `MINIAN_FILE_PATTERN` if your videos are
named differently). For the example session the behavior camera ran at **~47 fps**, not 20 —
set the fps accordingly in eztrack and `capstone/config/data_paths.yaml`.

## Two sessions

- **`prerecorded`** — the backup dataset, always available from the archive. Use
  this so the workshop runs even if a live recording doesn't happen.
- **`live`** — recorded during the workshop and uploaded to the archive if that
  works out. Its DOI isn't known until then, so pass it at fetch time with
  `--doi` (no code edit, no `git pull`): `--session live --doi <DOI>`.

Participants can pull **one or both** — just run the command once per session
they want.

## Download

```bash
python scripts/get_data.py                              # prerecorded, all stages
python scripts/get_data.py --what raw                   # just the raw recording (feeds Minian + eztrack)
python scripts/get_data.py --what processed             # minian_out + deconv_out + eztrack_out
python scripts/get_data.py --what minian_out            # a single processed stage
python scripts/get_data.py --session live --doi <DOI>                  # the workshop recording
python scripts/get_data.py --force                      # re-download even if local data exists
```

`--what` takes a **group** (`raw`, `processed`, `all`) **or a single stage name**
(`minian_out`, `deconv_out`, `eztrack_out`). Single-stage is for when you
produced the other stages yourself — e.g. you tracked behavior in eztrack but
want the canonical Minian output: `--what minian_out` pulls only that, and
nothing downloads as a zip you have to open — each stage extracts straight into
`data/sessions/<session>/<stage>/`, ready to use (the downloaded zip is kept in
`data/.cache/` only to avoid re-downloading).

## Getting the live recording (day 2)

The `prerecorded` session is already published, so `python scripts/get_data.py`
just works from day one. The **live** session is the recording made *during* the
workshop, so it's published partway through. To get it, the organizer will hand
you **one** of these — you only do the one you're told:

- **A DOI to paste** — run this once (replace `<DOI>` with the string given):

  ```bash
  python scripts/get_data.py --session live --doi <DOI>
  ```

- **"Pull the repo"** — if the organizer baked the DOI into the repo instead,
  update your copy and then fetch with no DOI needed:

  ```bash
  git pull
  python scripts/get_data.py --session live
  ```

Either way the data lands in `data/sessions/live/`, and every notebook works the
same once you point it at the `live` session (set `SESSION = "live"` in the
notebook's first cell, or swap `prerecorded` → `live` in the path).

## Local-first resolution

Each stage is a separate bundle, fetched **local-first**:

- **Raw** (videos + timestamps) is the input to Minian (step 2) and eztrack (step 4).
- **Processed** stages (`minian_out`, `deconv_out`, `eztrack_out`) feed calab
  (step 3) and the CaMAP capstone (step 5). Their inputs can be either *your own
  local output* from running the upstream step **or** the processed bundle from
  the archive.

`get_data.py` keeps any stage you already produced and downloads only the missing
ones. So a participant who ran Minian uses their own `minian_out/`, while someone
who skipped it pulls the archived copy — both land at the same path, and the
capstone doesn't care which.

## Timestamps

`raw/` includes the **Miniscope DAQ** timestamp CSVs (`neural_timestamp.csv`,
`behavior_timestamp.csv`) — not produced by Minian or eztrack. CaMAP's
`match_events()` needs them to align behavior onto the neural clock, and the
neural timestamp file must have the same frame count as Minian's `C.zarr`.

Organizer prep and pending tasks live in [`ORGANIZER.md`](../ORGANIZER.md).
