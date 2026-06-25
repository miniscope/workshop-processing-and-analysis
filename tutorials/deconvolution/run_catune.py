"""Bridge Minian traces -> CaTune (browser) -> deconvolved activity.

CaTune is interactive, so a real session runs in two phases:

  Phase 1 — send traces to the browser:
      python tutorials/deconvolution/run_catune.py --session prerecorded
    Converts Minian's C.zarr to a CaTune .npy, opens CaTune with those traces
    over a localhost bridge. Tune the parameters, then EXPORT the params JSON
    and download it.

  Phase 2 — apply the tuned params and save:
      python tutorials/deconvolution/run_catune.py --session prerecorded --params <export.json>
    Applies the exported params and writes deconv_out/activity.npy (shape
    (n_cells, n_frames)).

No data? Use ``--demo`` to just open the hosted CaTune landing page so you can
generate simulated traces and pick parameters yourself, all in the browser:

      python tutorials/deconvolution/run_catune.py --demo

Thin wrapper over the `calab` CLI (convert / tune / deconvolve).
"""

from __future__ import annotations

import argparse
import sys
import webbrowser
from pathlib import Path

from _calab_common import (
    REPO_ROOT,
    TRACE_HELP,
    convert_minian_traces,
    deconv_dir,
    find_calab,
    run,
)

# Hosted CaTune app (GitHub Pages); generates its own simulated data in-browser.
CATUNE_URL = "https://miniscope.github.io/CaLab/CaTune/"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--session", default="prerecorded")
    ap.add_argument("--fs", type=float, default=20.0, help="neural sampling rate (Hz)")
    ap.add_argument("--trace", default="C", help=TRACE_HELP)
    ap.add_argument("--demo", action="store_true",
                    help="just open the hosted CaTune landing page (simulate in-browser, no data)")
    ap.add_argument("--params", help="CaTune export JSON to apply (phase 2)")
    args = ap.parse_args()

    if args.demo:
        # Pure exploration: open the app so the user drives the in-browser
        # simulator and parameter selection. No bridge, no session data, and
        # nothing to save back (the demo traces live only in the browser).
        if args.params:
            print("Note: --params is ignored with --demo (demo data lives in the "
                  "browser; there's nothing to deconvolve from Python).")
        print(f"Opening CaTune: {CATUNE_URL}")
        print("Use the app's built-in simulator to generate traces and tune "
              "parameters yourself — no data file needed.")
        webbrowser.open(CATUNE_URL)
        return 0

    calab_exe = find_calab()
    deconv = deconv_dir(args.session)
    traces_npy = deconv / "traces.npy"
    activity = deconv / "activity.npy"

    if args.params:
        # Phase 2: apply exported params -> activity.npy
        if not Path(args.params).is_file():
            sys.exit(f"params file not found: {args.params} — this is the JSON you "
                     f"EXPORTed from CaTune (usually in your Downloads folder).")
        if not traces_npy.exists():
            sys.exit(f"{traces_npy} missing — run phase 1 first.")
        rc = run([calab_exe, "deconvolve", str(traces_npy), "-p", args.params, "-o", str(activity)])
        if rc == 0:
            print(f"\nSaved deconvolved activity -> {activity}")
        return rc

    # Phase 1: convert Minian C.zarr -> traces.npy, then open CaTune
    traces_npy = convert_minian_traces(calab_exe, args.session, args.trace, args.fs)

    print(f"\nOpening CaTune for {traces_npy} ...")
    print("Tune parameters in the browser, EXPORT the params JSON, then re-run:")
    rel = Path(__file__).relative_to(REPO_ROOT).as_posix()
    print(f"  python {rel} --session {args.session} --params <downloaded_export.json>\n")
    return run([calab_exe, "tune", str(traces_npy), "--fs", str(args.fs)])


if __name__ == "__main__":
    sys.exit(main())
