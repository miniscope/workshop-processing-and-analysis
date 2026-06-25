"""Bridge Minian traces -> CaDecon (browser, automated) -> deconvolved activity.

    python tutorials/deconvolution/run_cadecon.py --session prerecorded

Converts Minian's C.zarr to a CaDecon .npy, opens CaDecon with those traces
over a localhost bridge, and on completion writes ``activity.npy`` (shape
``(n_cells, n_frames)``) to the session's ``deconv_out/``.

No data? Use ``--demo`` to just open the hosted CaDecon landing page so you can
generate simulated traces and choose deconvolution settings yourself, all in
the browser:

    python tutorials/deconvolution/run_cadecon.py --demo

Thin wrapper over the `calab` CLI (convert / cadecon).
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import webbrowser
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# Hosted CaDecon app (GitHub Pages); generates its own simulated data in-browser.
CADECON_URL = "https://miniscope.github.io/CaLab/CaDecon/"


def run(cmd: list[str]) -> int:
    print("  $", " ".join(cmd))
    return subprocess.run(cmd).returncode


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
                    help="just open the hosted CaDecon landing page (simulate in-browser, no data)")
    args = ap.parse_args()

    if args.demo:
        # Pure exploration: open the app so the user drives the in-browser
        # simulator and settings. No bridge, no session data, nothing saved
        # back (the demo traces live only in the browser).
        print(f"Opening CaDecon: {CADECON_URL}")
        print("Use the app's built-in simulator to generate traces and choose "
              "deconvolution settings yourself — no data file needed.")
        webbrowser.open(CADECON_URL)
        return 0

    calab_exe = shutil.which("calab")
    if calab_exe is None:
        sys.exit("calab not found — activate the workshop venv (pip install calab).")

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
