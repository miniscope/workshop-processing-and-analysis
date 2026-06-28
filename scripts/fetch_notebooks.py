"""Refresh each tool's teaching notebooks in tutorials/<tool>/notebooks/.

A **known-good copy of every teaching notebook is committed to the repo**, so
they are present the moment you clone — nothing has to succeed for the workshop
materials to exist. This script is an *optional refresh*: the upstream packages
(minisim, Minian, eztrack) ship their teaching notebooks inside the installed
wheel and expose a CLI to copy them out, version-matched to whatever you have
installed. Run it to pull the copies that match your installed versions.

Run from the repo root with the workshop venv active:

    python scripts/fetch_notebooks.py

It is **non-destructive**: each tool is fetched into a temporary directory and
only swapped into place if the copy succeeds and yields at least one notebook.
If a tool's fetch fails (CLI missing, upstream drift, no network), the committed
copy already in tutorials/<tool>/notebooks/ is left untouched — a failed or
repeated run can never leave you with fewer notebooks than you started with.
A nonzero exit means at least one tool could not be refreshed.

Notes:
- calab (CaTune / CaDecon) ships no notebooks upstream. The workshop's
  deconvolution notebook (tutorials/deconvolution/deconvolution.ipynb) is
  authored in the repo, not fetched — see tutorials/deconvolution/README.md.
- The CaMAP capstone notebook lives in the repo (capstone/), not upstream.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# (label, console-script command prefix, destination under tutorials/)
# Each tool's `notebooks copy --all -o DEST` writes one subfolder per bundle.
TOOLS: list[tuple[str, list[str], Path]] = [
    ("minisim", ["minisim-notebooks", "copy", "--all", "-o"], REPO_ROOT / "tutorials/minisim/notebooks"),
    ("minian", ["minian", "notebooks", "copy", "--all", "-o"], REPO_ROOT / "tutorials/minian/notebooks"),
    ("eztrack", ["eztrack", "notebooks", "copy", "--all", "-o"], REPO_ROOT / "tutorials/eztrack/notebooks"),
]


def fetch(label: str, cmd_prefix: list[str], dest: Path) -> bool:
    """Refresh one tool's notebooks into *dest*. Returns True on success.

    Fetches into a temp dir and swaps it into place only if the copy produced
    at least one notebook, so a failure leaves the committed copy untouched.
    """
    exe = shutil.which(cmd_prefix[0])
    if exe is None:
        print(f"  SKIP {label}: '{cmd_prefix[0]}' not found — is the venv active and {label} installed? "
              f"(keeping the committed copy in {dest.relative_to(REPO_ROOT)})")
        return False

    dest.parent.mkdir(parents=True, exist_ok=True)
    # Stage in a sibling temp dir (same filesystem, so the swap is a cheap move).
    tmp = Path(tempfile.mkdtemp(prefix=f".{dest.name}.", dir=dest.parent))
    try:
        cmd = [exe, *cmd_prefix[1:], str(tmp)]
        result = subprocess.run(cmd, cwd=REPO_ROOT)
        if result.returncode != 0:
            print(f"  FAIL {label}: '{' '.join(cmd_prefix)} ...' exited {result.returncode} "
                  f"(kept the committed copy in {dest.relative_to(REPO_ROOT)})")
            return False

        n = len(list(tmp.rglob("*.ipynb")))
        if n == 0:
            print(f"  FAIL {label}: fetch produced no .ipynb files "
                  f"(kept the committed copy in {dest.relative_to(REPO_ROOT)})")
            return False

        # Swap in the fresh copy: remove the old, move the staged one into place.
        if dest.exists():
            shutil.rmtree(dest)
        shutil.move(str(tmp), str(dest))
        tmp = None  # consumed by the move; nothing left to clean up
        print(f"  OK   {label}: {n} notebook(s) -> {dest.relative_to(REPO_ROOT)}")
        return True
    finally:
        if tmp is not None and tmp.exists():
            shutil.rmtree(tmp, ignore_errors=True)


def main() -> int:
    print("Refreshing teaching notebooks in tutorials/<tool>/notebooks/ ...")
    print("(committed copies are used as-is if a tool can't be refreshed)\n")
    ok = sum(fetch(*t) for t in TOOLS)
    print(f"\n{ok}/{len(TOOLS)} tools refreshed. Open them with: jupyter lab")
    if ok != len(TOOLS):
        print("\nNot all tools refreshed (see SKIP/FAIL above). The committed copies are\n"
              "still in place, so the notebooks are present — but they may not match your\n"
              "installed versions. Activate the workshop venv and re-run if you need a\n"
              "version-matched refresh.")
    print("\ncalab (CaTune/CaDecon): use tutorials/deconvolution/deconvolution.ipynb "
          "(authored in-repo) or `calab tune` / `calab cadecon`.")
    return 0 if ok == len(TOOLS) else 1


if __name__ == "__main__":
    sys.exit(main())
