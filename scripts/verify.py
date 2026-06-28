"""Pre-flight self-check for the workshop install.

Run this AFTER following INSTALL.md, with the workshop venv active:

    python scripts/verify.py

It does not install or download anything - it just checks that each install
step actually worked and prints one PASS / FAIL / WARN per check, with the exact
command to fix anything that's red. Send the output (or a screenshot of an
all-PASS run) to the organizers before the workshop so a broken setup is found
days early, not in the room.

Exit code is 0 only if every required check passed.
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Tool distributions to confirm, with the version pinned in requirements.lock
# (a mismatch is a WARN, not a failure - newest-from-PyPI installs are allowed).
TOOLS = {
    "minisim": "1.0.3",
    "minian": "2.0.2",
    "calab": "0.2.3",
    "camap": "0.1.6",
    "eztrack": None,  # git fork - no PyPI version to compare against
}

# Teaching-notebook dirs that must hold at least one .ipynb.
NOTEBOOK_DIRS = ["minisim", "minian", "eztrack"]

# Files the capstone needs from the prerecorded session.
SESSION = REPO_ROOT / "data" / "sessions" / "prerecorded"
DATA_INPUTS = [
    SESSION / "minian_out",
    SESSION / "deconv_out",
    SESSION / "eztrack_out",
    SESSION / "raw" / "neural_timestamp.csv",
    SESSION / "raw" / "behavior_timestamp.csv",
]

_results: list[tuple[str, str, str]] = []  # (status, label, hint)


def record(status: str, label: str, hint: str = "") -> None:
    _results.append((status, label, hint))
    line = f"  [{status:4}] {label}"
    print(line if not hint else f"{line}\n         -> {hint}")


def _nonempty_dir(p: Path) -> bool:
    return p.is_dir() and any(p.iterdir())


def check_python() -> None:
    v = sys.version_info
    ok = (3, 11) <= (v.major, v.minor) <= (3, 13)
    label = f"Python {v.major}.{v.minor}.{v.micro} (need 3.11-3.13)"
    record("PASS" if ok else "FAIL", label,
            "" if ok else "Install Python 3.11-3.13 (3.12 recommended) - see INSTALL.md Step 0.")


def check_venv() -> None:
    in_venv = sys.prefix != getattr(sys, "base_prefix", sys.prefix) or "VIRTUAL_ENV" in os.environ
    record("PASS" if in_venv else "WARN",
           f"virtual env active ({Path(sys.prefix).name})",
           "" if in_venv else "Activate the venv first (INSTALL.md Step 2), or you may be checking the wrong Python.")


def check_ffmpeg() -> None:
    exe = shutil.which("ffmpeg")
    record("PASS" if exe else "FAIL", "ffmpeg on PATH",
           "" if exe else "Install ffmpeg (INSTALL.md Step 0) and open a new terminal so PATH refreshes.")


def check_tools() -> None:
    from importlib.metadata import PackageNotFoundError, version
    for dist, pinned in TOOLS.items():
        try:
            got = version(dist)
        except PackageNotFoundError:
            record("FAIL", f"package '{dist}' installed",
                   f"pip install -r requirements.lock  (then re-run). '{dist}' is missing.")
            continue
        if pinned and got != pinned:
            record("WARN", f"package '{dist}' {got} (lock pins {pinned})",
                   "Not fatal, but the room is pinned - `pip install -r requirements.lock` for the known-good set.")
        else:
            record("PASS", f"package '{dist}' {got}")


def check_kernel() -> None:
    try:
        from jupyter_client.kernelspec import KernelSpecManager
        specs = KernelSpecManager().find_kernel_specs()
    except Exception as exc:  # jupyter not installed, or spec dir unreadable
        record("FAIL", "Jupyter 'workshop' kernel registered",
               f"Could not query kernels ({type(exc).__name__}). "
               f"Install deps, then: python -m ipykernel install --user --name workshop --display-name \"Workshop\"")
        return
    ok = "workshop" in specs
    record("PASS" if ok else "FAIL", "Jupyter 'workshop' kernel registered",
           "" if ok else 'python -m ipykernel install --user --name workshop --display-name "Workshop"')


def check_notebooks() -> None:
    for tool in NOTEBOOK_DIRS:
        d = REPO_ROOT / "tutorials" / tool / "notebooks"
        n = len(list(d.rglob("*.ipynb"))) if d.exists() else 0
        record("PASS" if n else "FAIL", f"teaching notebooks: {tool} ({n} found)",
               "" if n else "python scripts/fetch_notebooks.py  (committed copies should already be present - check your clone).")


def check_data() -> None:
    missing = [p for p in DATA_INPUTS
               if not (_nonempty_dir(p) if p.suffix == "" else p.exists())]
    if missing:
        names = ", ".join(p.relative_to(SESSION).as_posix() for p in missing)
        record("WARN", "capstone data present",
               f"Missing: {names}. Run: python scripts/get_data.py --session prerecorded --skip-video")
    else:
        record("PASS", "capstone data present (prerecorded)")


def main() -> int:
    print("Workshop install self-check\n" + "=" * 27)
    print(f"repo: {REPO_ROOT}\npython: {sys.executable}\n")
    for check in (check_python, check_venv, check_ffmpeg, check_tools,
                  check_kernel, check_notebooks, check_data):
        try:
            check()
        except Exception as exc:  # never let the checker itself crash the gate
            record("FAIL", f"{check.__name__} crashed", f"{type(exc).__name__}: {exc}")

    fails = [r for r in _results if r[0] == "FAIL"]
    warns = [r for r in _results if r[0] == "WARN"]
    passes = [r for r in _results if r[0] == "PASS"]
    print("\n" + "-" * 27)
    print(f"{len(passes)} passed, {len(warns)} warning(s), {len(fails)} failed.")
    if fails:
        print("\nNOT READY - fix the FAIL items above and re-run. Send this output to the organizers if stuck.")
        return 1
    if warns:
        print("\nReady, with warnings (see WARN above) - usually fine, but worth a look.")
    else:
        print("\nAll checks passed - you're ready for the workshop.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
