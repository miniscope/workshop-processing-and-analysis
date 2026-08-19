# Organizer checklist (not for participants)

Pre-workshop prep and open verification items, collected here so the
participant-facing READMEs stay clean. Each item links back to the module it
came from.

## Participant install — pre-flight gate

Make a passing self-check a **prerequisite**, so broken setups surface days early
over email — not in a time-boxed room where one stuck laptop blocks everyone.

- [ ] Send the install link ([INSTALL.md](INSTALL.md)) with a deadline (e.g. 2
      days out): clone → `pip install -r requirements.lock` → register the
      `workshop` kernel → `python scripts/get_data.py` → **`python scripts/verify.py`**,
      and reply with the output (or an all-`PASS` screenshot).
- [ ] Triage anyone who's red over email or a pre-workshop office hour.
- [ ] **Dry-run the full install on a clean machine of each OS family** you expect
      (Windows, macOS Apple-Silicon, macOS Intel, Linux). The lock is verified on
      Linux by CI but is **untested on macOS/ARM** — this dry run, not CI, is the
      real cross-OS guarantee. If a pinned package has no wheel on some platform,
      patch `requirements.lock` (env marker) before sending instructions.

## Data & archive — [`data/README.md`](data/README.md)

- [x] Publish the `prerecorded` deposit and set its DOI in `scripts/get_data.py`
      (`SESSIONS["prerecorded"]` = `10.25346/S6SGHPCZ`, UCLA Dataverse). Filenames
      + checksums are read from the DOI — nothing else to fill.
- [x] Smoke-test `get_data.py` against the real DOI (resolves + downloads, MD5-verified).
- [x] Build + upload the processed bundles as `minian_out.zip`, `deconv_out.zip`,
      `eztrack_out.zip` (each zip's **contents at the top level**, no wrapping
      folder, so they extract straight into the stage dir). Done — uploaded to the
      `prerecorded` deposit (double-zipped so Dataverse keeps each `*_out.zip`
      intact) and verified to download + extract via `get_data.py --what processed`.
- [ ] **Archive downloads are currently broken, instance-wide.** Every file in
      the `prerecorded` deposit returns `404 Failed to locate and/or open
      physical file` from `dataverse.ucla.edu/api/access/datafile/<id>` (all 33
      files, all three dataset versions; the whole-dataset zip 500s). It is not
      our deposit: the same failure reproduces on unrelated public datasets on
      the same instance (e.g. UCLA Registrar data, datafile 20383). Metadata
      resolves fine, so this is storage-side. **File a ticket with UCLA
      Dataverse support** — lead with "instance-wide, reproducible on datasets
      we don't own", which routes to infrastructure rather than to a curator
      checking our upload.
- [ ] **Publish a mirror** so the workshop does not depend on one archive.
      **figshare first** (`scripts/publish_figshare.py`) — it downloads ~11x
      faster than Zenodo (measured 6.6 vs 0.6 MB/s), which is what matters for
      a room pulling 9 GB; Zenodo (`scripts/publish_zenodo.py`) is the slow,
      CERN-backed preservation copy. Both: `--dry-run` to check what goes up,
      then bare to upload a draft, then `--publish` to mint the DOI. Add that
      DOI to `SESSIONS["prerecorded"]` in `scripts/get_data.py` and fetches
      fail over automatically — see
      [Mirrors and archive outages](data/README.md#mirrors-and-archive-outages).
      Tokens: `.figshare_token` / `.zenodo_token` (see the `.example` files).
      In flight: figshare draft article 33289752, Zenodo draft deposition
      22015414 — resume with `--article` / `--deposition` if interrupted.
- [x] **Recovery lever for a participant who breaks a stage:**
      `python scripts/get_data.py --restore --what minian_out` wipes the stage
      and re-extracts the published bundle from `data/.cache/` — instant and
      offline, since the first `get_data.py` run caches the zips. Worth
      demoing once at the start of the Minian block. See
      [Restoring a stage you broke](data/README.md#restoring-a-stage-you-broke).
- [ ] **Live session:** after the workshop recording, run `prepare_session.py` and
      upload to the archive, then either hand participants the DOI for
      `--session live --doi …`, or set `SESSIONS["live"]` in `scripts/get_data.py`
      and have them `git pull`. See "Getting the live recording" in
      [`data/README.md`](data/README.md#getting-the-live-recording-day-2).

## minisim — [`tutorials/minisim/README.md`](tutorials/minisim/README.md)

- [ ] Decide the running order in the agenda (training ladder first, then studio).

## Minian — [`tutorials/minian/README.md`](tutorials/minian/README.md)

- [x] Confirm `C.zarr` dim order / coords load cleanly in CaMAP and calab on real data.
- [x] Ensure `A.zarr` has valid unique `unit_id` coords (CaMAP disables the footprint overlay otherwise).
- [x] Point `dpath` at the workshop session's raw video (defaults to Minian's bundled demo).

## Deconvolution — [`tutorials/deconvolution/README.md`](tutorials/deconvolution/README.md)

- [x] Confirm `--fs` and the `C` vs `C_lp` trace name for the example session.
- [x] Confirm CaDecon's row order matches Minian `C` (the inject asserts this).

## eztrack — [`tutorials/eztrack/README.md`](tutorials/eztrack/README.md)

- [x] Confirm which eztrack export the example session uses (raw track vs scaled).

## Capstone — [`capstone/README.md`](capstone/README.md)

- [x] Verify the arena config (`config/`) matches the example session (fps, arena bounds, mm scale).
- [x] Run end-to-end once the example data lands in the archive (CI smoke test).
