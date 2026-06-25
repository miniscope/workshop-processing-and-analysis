"""Bridge Minian traces -> CaTune (browser) -> deconvolved activity.

CaTune is interactive, so this runs in two phases:

  Phase 1 — send traces to the browser:
      python tutorials/deconvolution/run_catune.py --session prerecorded
    Converts Minian's C.zarr to a CaTune .npy and opens CaTune. Tune the
    parameters, then EXPORT the params JSON from CaTune and download it.

  Phase 2 — apply the tuned params and save:
      python tutorials/deconvolution/run_catune.py --session prerecorded --params <export.json>
    Applies the exported params and writes data/sessions/<session>/deconv_out/activity.npy
    (shape (n_cells, n_frames)) — the file the capstone's deconv_inject reads.

Thin wrapper over the `calab` CLI (convert / tune / deconvolve).
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
    ap.add_argument("--params", help="CaTune export JSON to apply (phase 2)")
    args = ap.parse_args()

    calab = shutil.which("calab")
    if calab is None:
        sys.exit("calab not found — activate the workshop venv (pip install calab).")

    sess = REPO_ROOT / "data" / "sessions" / args.session
    czarr = sess / "minian_out" / f"{args.trace}.zarr"
    deconv = sess / "deconv_out"
    deconv.mkdir(parents=True, exist_ok=True)
    traces_npy = deconv / "traces.npy"
    activity = deconv / "activity.npy"

    if args.params:
        # Phase 2: apply exported params -> activity.npy
        if not traces_npy.exists():
            sys.exit(f"{traces_npy} missing — run phase 1 first.")
        rc = run([calab, "deconvolve", str(traces_npy), "-p", args.params, "-o", str(activity)])
        if rc == 0:
            print(f"\nSaved deconvolved activity -> {activity}")
        return rc

    # Phase 1: convert Minian C.zarr -> traces.npy, then open CaTune
    if not czarr.exists():
        sys.exit(f"{czarr} not found — run Minian or `python scripts/get_data.py` first.")
    if run([calab, "convert", "-f", "minian", str(czarr), "--fs", str(args.fs),
            "-o", str(deconv / "traces")]):
        return 1
    print(f"\nOpening CaTune for {traces_npy} ...")
    print("Tune parameters in the browser, EXPORT the params JSON, then re-run:")
    rel = Path(__file__).relative_to(REPO_ROOT).as_posix()
    print(f"  python {rel} --session {args.session} --params <downloaded_export.json>\n")
    return run([calab, "tune", str(traces_npy), "--fs", str(args.fs)])


if __name__ == "__main__":
    sys.exit(main())
