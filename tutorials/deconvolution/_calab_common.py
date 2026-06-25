"""Shared helpers for the calab (CaTune / CaDecon) workshop wrappers.

``run_catune.py`` and ``run_cadecon.py`` are thin wrappers over the same
``calab`` CLI and share the session-path layout, the convert-to-traces step,
and the "calab not installed" check. Keeping that logic here means the convert
invocation and its error messages live in one place.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# Shared --trace help: novices shouldn't have to know Minian internals to pick.
TRACE_HELP = "Minian trace to deconvolve; keep the default C (raw denoised) — C_lp is for display only."


def run(cmd: list[str]) -> int:
    """Echo a command, run it, and return its exit code."""
    print("  $", " ".join(cmd))
    return subprocess.run(cmd).returncode


def find_calab() -> str:
    """Return the path to the ``calab`` console script, or exit with guidance."""
    exe = shutil.which("calab")
    if exe is None:
        sys.exit("calab not found — activate the workshop venv (pip install calab).")
    return exe


def deconv_dir(session: str) -> Path:
    """The session's ``deconv_out/`` directory (not created)."""
    return REPO_ROOT / "data" / "sessions" / session / "deconv_out"


def convert_minian_traces(calab_exe: str, session: str, trace: str, fs: float) -> Path:
    """Convert a session's Minian ``<trace>.zarr`` to ``deconv_out/traces.npy``.

    Returns the path to the written ``traces.npy``.
    """
    czarr = REPO_ROOT / "data" / "sessions" / session / "minian_out" / f"{trace}.zarr"
    if not czarr.exists():
        sys.exit(f"{czarr} not found — run Minian / `python scripts/get_data.py`, or use --demo.")
    deconv = deconv_dir(session)
    deconv.mkdir(parents=True, exist_ok=True)
    if run([calab_exe, "convert", "-f", "minian", str(czarr), "--fs", str(fs),
            "-o", str(deconv / "traces")]):
        sys.exit("convert failed")
    return deconv / "traces.npy"
