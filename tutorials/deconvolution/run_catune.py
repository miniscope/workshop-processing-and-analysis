"""Bridge Minian traces -> CaTune (browser) -> deconvolved activity.

CaTune is interactive, so this runs in two phases:

  Phase 1 — send traces to the browser:
      python tutorials/deconvolution/run_catune.py --session prerecorded
      python tutorials/deconvolution/run_catune.py --demo        # no data needed
    With a session, converts Minian's C.zarr to a CaTune .npy. With ``--demo`` it
    generates synthetic traces via ``calab.simulate()`` instead — handy for just
    bringing up CaTune with no recording on hand. Opens CaTune; tune the
    parameters, then EXPORT the params JSON and download it.

  Phase 2 — apply the tuned params and save:
      python tutorials/deconvolution/run_catune.py [--session ... | --demo] --params <export.json>
    Applies the exported params and writes activity.npy (shape (n_cells, n_frames))
    next to the traces — the session's deconv_out/ for a real run, or
    data/.cache/demo_catune/ for --demo.

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


def demo_traces(work: Path) -> Path:
    """Generate simulated traces (no session data needed) -> work/traces.npy."""
    import calab
    import numpy as np

    work.mkdir(parents=True, exist_ok=True)
    npy = work / "traces.npy"
    print("Generating simulated traces with calab.simulate() ...")
    np.save(npy, np.ascontiguousarray(calab.simulate().traces, dtype=np.float64))
    return npy


def work_dir(args: argparse.Namespace) -> Path:
    if args.demo:
        return REPO_ROOT / "data" / ".cache" / "demo_catune"
    return REPO_ROOT / "data" / "sessions" / args.session / "deconv_out"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--session", default="prerecorded")
    ap.add_argument("--fs", type=float, default=20.0, help="neural sampling rate (Hz)")
    ap.add_argument("--trace", default="C", help="Minian zarr store name (C or C_lp)")
    ap.add_argument("--demo", action="store_true",
                    help="use calab-simulated traces instead of session data")
    ap.add_argument("--params", help="CaTune export JSON to apply (phase 2)")
    args = ap.parse_args()

    calab_exe = shutil.which("calab")
    if calab_exe is None:
        sys.exit("calab not found — activate the workshop venv (pip install calab).")

    deconv = work_dir(args)
    traces_npy = deconv / "traces.npy"
    activity = deconv / "activity.npy"

    if args.params:
        # Phase 2: apply exported params -> activity.npy
        if not traces_npy.exists():
            sys.exit(f"{traces_npy} missing — run phase 1 first.")
        rc = run([calab_exe, "deconvolve", str(traces_npy), "-p", args.params, "-o", str(activity)])
        if rc == 0:
            print(f"\nSaved deconvolved activity -> {activity}")
        return rc

    # Phase 1: prepare traces, then open CaTune
    if args.demo:
        demo_traces(deconv)
    else:
        czarr = REPO_ROOT / "data" / "sessions" / args.session / "minian_out" / f"{args.trace}.zarr"
        if not czarr.exists():
            sys.exit(f"{czarr} not found — run Minian / `python scripts/get_data.py`, or use --demo.")
        deconv.mkdir(parents=True, exist_ok=True)
        if run([calab_exe, "convert", "-f", "minian", str(czarr), "--fs", str(args.fs),
                "-o", str(deconv / "traces")]):
            return 1

    print(f"\nOpening CaTune for {traces_npy} ...")
    print("Tune parameters in the browser, EXPORT the params JSON, then re-run:")
    rel = Path(__file__).relative_to(REPO_ROOT).as_posix()
    demo_flag = " --demo" if args.demo else f" --session {args.session}"
    print(f"  python {rel}{demo_flag} --params <downloaded_export.json>\n")
    return run([calab_exe, "tune", str(traces_npy), "--fs", str(args.fs)])


if __name__ == "__main__":
    sys.exit(main())
