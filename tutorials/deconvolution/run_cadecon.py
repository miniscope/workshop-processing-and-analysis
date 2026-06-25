"""Bridge Minian traces -> CaDecon (browser, automated) -> deconvolved activity.

    python tutorials/deconvolution/run_cadecon.py --session prerecorded
    python tutorials/deconvolution/run_cadecon.py --demo      # no data needed

With a session, converts Minian's C.zarr to a CaDecon .npy. With ``--demo`` it
generates synthetic traces via ``calab.simulate()`` instead — handy for just
bringing up the CaDecon browser interface with no recording on hand. Either way
it opens CaDecon and, on completion, writes ``activity.npy`` (shape
``(n_cells, n_frames)``) next to the traces (the session's ``deconv_out/`` for a
real run, or ``data/.cache/demo_cadecon/`` for ``--demo``).

Thin wrapper over the `calab` CLI (convert / cadecon).
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def run(cmd: list[str]) -> int:
    print("  $", " ".join(cmd))
    return subprocess.run(cmd).returncode


def demo_traces(work: Path) -> Path:
    """Generate simulated traces (no session data needed) and save to work/traces.npy."""
    import calab
    import numpy as np

    work.mkdir(parents=True, exist_ok=True)
    npy = work / "traces.npy"
    print("Generating simulated traces with calab.simulate() ...")
    np.save(npy, np.ascontiguousarray(calab.simulate().traces, dtype=np.float64))
    return npy


def minian_traces(calab_exe: str, session: str, trace: str, fs: float) -> tuple[Path, Path]:
    """Convert a session's Minian C.zarr to traces.npy in its deconv_out/."""
    sess = REPO_ROOT / "data" / "sessions" / session
    czarr = sess / "minian_out" / f"{trace}.zarr"
    deconv = sess / "deconv_out"
    deconv.mkdir(parents=True, exist_ok=True)
    if not czarr.exists():
        sys.exit(f"{czarr} not found — run Minian / `python scripts/get_data.py`, or use --demo.")
    if run([calab_exe, "convert", "-f", "minian", str(czarr), "--fs", str(fs),
            "-o", str(deconv / "traces")]):
        sys.exit("convert failed")
    return deconv / "traces.npy", deconv


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--session", default="prerecorded")
    ap.add_argument("--fs", type=float, default=20.0, help="neural sampling rate (Hz)")
    ap.add_argument("--trace", default="C", help="Minian zarr store name (C or C_lp)")
    ap.add_argument("--demo", action="store_true",
                    help="use calab-simulated traces instead of session data")
    args = ap.parse_args()

    calab_exe = shutil.which("calab")
    if calab_exe is None:
        sys.exit("calab not found — activate the workshop venv (pip install calab).")

    if args.demo:
        deconv = REPO_ROOT / "data" / ".cache" / "demo_cadecon"
        traces_npy = demo_traces(deconv)
    else:
        traces_npy, deconv = minian_traces(calab_exe, args.session, args.trace, args.fs)

    # CaDecon writes {stem}_activity.npy + {stem}_results.json
    if run([calab_exe, "cadecon", str(traces_npy), "--fs", str(args.fs),
            "-o", str(deconv / "cadecon")]):
        return 1

    src = deconv / "cadecon_activity.npy"
    dst = deconv / "activity.npy"
    if not src.exists():
        sys.exit(f"expected {src} not found — did CaDecon finish?")
    shutil.copyfile(src, dst)
    print(f"\nSaved deconvolved activity -> {dst}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
