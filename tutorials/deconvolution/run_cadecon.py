"""Bridge Minian traces -> CaDecon (browser, automated) -> deconvolved activity.

    python tutorials/deconvolution/run_cadecon.py --session prerecorded

Converts Minian's C.zarr to a CaDecon .npy, opens CaDecon (automated
deconvolution), and on completion writes
data/sessions/<session>/deconv_out/activity.npy (shape (n_cells, n_frames)) —
the file the capstone's deconv_inject reads. CaDecon also leaves its native
`cadecon_activity.npy` + `cadecon_results.json` (kernels, baselines, PVEs).

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


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--session", default="prerecorded")
    ap.add_argument("--fs", type=float, default=20.0, help="neural sampling rate (Hz)")
    ap.add_argument("--trace", default="C", help="Minian zarr store name (C or C_lp)")
    args = ap.parse_args()

    calab = shutil.which("calab")
    if calab is None:
        sys.exit("calab not found — activate the workshop venv (pip install calab).")

    sess = REPO_ROOT / "data" / "sessions" / args.session
    czarr = sess / "minian_out" / f"{args.trace}.zarr"
    deconv = sess / "deconv_out"
    deconv.mkdir(parents=True, exist_ok=True)
    traces_npy = deconv / "traces.npy"

    if not czarr.exists():
        sys.exit(f"{czarr} not found — run Minian or `python scripts/get_data.py` first.")
    if run([calab, "convert", "-f", "minian", str(czarr), "--fs", str(args.fs),
            "-o", str(deconv / "traces")]):
        return 1
    # CaDecon writes {stem}_activity.npy + {stem}_results.json
    if run([calab, "cadecon", str(traces_npy), "--fs", str(args.fs),
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
