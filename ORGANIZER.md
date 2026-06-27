# Organizer checklist (not for participants)

Pre-workshop prep and open verification items, collected here so the
participant-facing READMEs stay clean. Each item links back to the module it
came from.

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
- [ ] **Live session:** after the workshop recording, run `prepare_session.py` and
      upload to the archive, then either hand participants the DOI for
      `--session live --doi …`, or set `SESSIONS["live"]` in `scripts/get_data.py`
      and have them `git pull`. See "Getting the live recording" in
      [`data/README.md`](data/README.md#getting-the-live-recording-day-2).

## minisim — [`tutorials/minisim/README.md`](tutorials/minisim/README.md)

- [ ] Decide the running order in the agenda (training ladder first, then studio).

## Minian — [`tutorials/minian/README.md`](tutorials/minian/README.md)

- [ ] Confirm `C.zarr` dim order / coords load cleanly in CaMAP and calab on real data.
- [ ] Ensure `A.zarr` has valid unique `unit_id` coords (CaMAP disables the footprint overlay otherwise).
- [ ] Point `dpath` at the workshop session's raw video (defaults to Minian's bundled demo).

## Deconvolution — [`tutorials/deconvolution/README.md`](tutorials/deconvolution/README.md)

- [ ] Confirm `--fs` and the `C` vs `C_lp` trace name for the example session.
- [ ] Confirm CaDecon's row order matches Minian `C` (the inject asserts this).

## eztrack — [`tutorials/eztrack/README.md`](tutorials/eztrack/README.md)

- [ ] Confirm which eztrack export the example session uses (raw track vs scaled).

## Capstone — [`capstone/README.md`](capstone/README.md)

- [ ] Verify the arena config (`config/`) matches the example session (fps, arena bounds, mm scale).
- [ ] Run end-to-end once the example data lands in the archive (CI smoke test).
