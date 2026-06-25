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
import sys
import webbrowser

from _calab_common import TRACE_HELP, convert_minian_traces, deconv_dir, find_calab, run

# Hosted CaDecon app (GitHub Pages); generates its own simulated data in-browser.
CADECON_URL = "https://miniscope.github.io/CaLab/CaDecon/"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--session", default="prerecorded")
    ap.add_argument("--fs", type=float, default=20.0, help="neural sampling rate (Hz)")
    ap.add_argument("--trace", default="C", help=TRACE_HELP)
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

    calab_exe = find_calab()
    deconv = deconv_dir(args.session)
    traces_npy = convert_minian_traces(calab_exe, args.session, args.trace, args.fs)

    # CaDecon writes {stem}_activity.npy + {stem}_results.json
    if run([calab_exe, "cadecon", str(traces_npy), "--fs", str(args.fs),
            "-o", str(deconv / "cadecon")]):
        return 1

    dst = deconv / "activity.npy"
    src = deconv / "cadecon_activity.npy"
    if not src.exists():
        # Tolerate a changed calab output name rather than misreporting it as
        # "didn't finish": take any *_activity.npy it left behind.
        hits = sorted(deconv.glob("*_activity.npy"))
        if not hits:
            sys.exit(f"expected {src} not found — did CaDecon finish?")
        src = hits[0]
    shutil.copyfile(src, dst)
    print(f"\nSaved deconvolved activity -> {dst}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
