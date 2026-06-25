"""Materialize each tool's teaching notebooks into its tutorials/<tool>/notebooks/.

The upstream packages (minisim, Minian, eztrack) ship their teaching notebooks
*inside the installed wheel* and expose a CLI to copy them out, version-matched
to whatever is installed. Rather than vendoring (and going stale), we fetch them
on demand into the repo so workshop participants have them right next to each
module's README.

Run from the repo root with the workshop venv active:

    python scripts/fetch_notebooks.py

Re-running refreshes the copies (each destination is cleared first). The fetched
folders are gitignored — they are generated, not committed.

Notes:
- calab (CaTune / CaDecon) ships no notebooks; it is launched (`calab tune` /
  `calab cadecon`) — see tutorials/deconvolution/README.md.
- The CaMAP capstone notebook lives in the repo (capstone/), not upstream.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
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
    """Copy one tool's notebooks into *dest*. Returns True on success."""
    exe = shutil.which(cmd_prefix[0])
    if exe is None:
        print(f"  SKIP {label}: '{cmd_prefix[0]}' not found — is the venv active and {label} installed?")
        return False

    # Idempotent: clear any previous copy (minian/eztrack copy has no --force).
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True, exist_ok=True)

    cmd = [exe, *cmd_prefix[1:], str(dest)]
    result = subprocess.run(cmd, cwd=REPO_ROOT)
    if result.returncode != 0:
        print(f"  FAIL {label}: '{' '.join(cmd_prefix)} ...' exited {result.returncode}")
        return False

    n = len(list(dest.rglob("*.ipynb")))
    print(f"  OK   {label}: {n} notebook(s) -> {dest.relative_to(REPO_ROOT)}")
    return True


def main() -> int:
    print("Fetching teaching notebooks into tutorials/<tool>/notebooks/ ...")
    ok = sum(fetch(*t) for t in TOOLS)
    print(f"\n{ok}/{len(TOOLS)} tools fetched. Open them with: jupyter lab")
    print("calab (CaTune/CaDecon) has no notebooks - launch with `calab tune` / `calab cadecon`.")
    return 0 if ok == len(TOOLS) else 1


if __name__ == "__main__":
    sys.exit(main())
