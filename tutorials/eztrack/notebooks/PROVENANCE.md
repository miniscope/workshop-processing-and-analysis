# Vendored notebooks — ezTrack

These teaching notebooks are **copied from the `eztrack` package**, not authored
here. They ship inside the installed wheel; `eztrack notebooks copy --all` writes
them out, and `scripts/fetch_notebooks.py` automates that.

- **Source:** the eztrack fork installed from git
  (`eztrack @ git+https://github.com/daharoni/ezTrack`, see `requirements.txt`).
- **License:** as distributed by ezTrack (GPL-3.0). Redistributed here under the
  same terms; copyright remains with the ezTrack authors.
- **Refresh:** `python scripts/fetch_notebooks.py` (non-destructive — it replaces
  these only if a version-matched copy is fetched successfully).

They are committed so the workshop materials are present on clone even if a live
fetch can't run. If you change a notebook here, your edit is overwritten on the
next successful refresh.
