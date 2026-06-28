# Vendored notebooks — Minian

These teaching notebooks are **copied from the `minian` package**, not authored
here. They ship inside the installed wheel; `minian notebooks copy --all` writes
them out, and `scripts/fetch_notebooks.py` automates that.

- **Source:** the `minian` package (see `requirements.txt`); version pinned in
  `requirements.lock` (`minian==2.0.2`).
- **License:** as distributed by Minian (GPL-3.0). Redistributed here under the
  same terms; copyright remains with the Minian authors.
- **Refresh:** `python scripts/fetch_notebooks.py` (non-destructive — it replaces
  these only if a version-matched copy is fetched successfully).

They are committed so the workshop materials are present on clone even if a live
fetch can't run. If you change a notebook here, your edit is overwritten on the
next successful refresh.
