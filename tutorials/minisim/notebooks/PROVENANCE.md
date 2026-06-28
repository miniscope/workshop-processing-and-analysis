# Vendored notebooks — minisim

These teaching notebooks are **copied from the `minisim` package**, not authored
here. They ship inside the installed wheel; `minisim-notebooks copy --all` writes
them out, and `scripts/fetch_notebooks.py` automates that.

- **Source:** the `minisim` package (see `requirements.txt`); version pinned in
  `requirements.lock` (`minisim==1.0.3`).
- **License:** as distributed by minisim (GPL-3.0-or-later). Redistributed here
  under the same terms; copyright remains with the minisim authors.
- **Refresh:** `python scripts/fetch_notebooks.py` (non-destructive — it replaces
  these only if a version-matched copy is fetched successfully).

They are committed so the workshop materials are present on clone even if a live
fetch can't run. If you change a notebook here, your edit is overwritten on the
next successful refresh.
