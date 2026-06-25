"""Convert eztrack position output into the DeepLabCut CSV format CaMAP reads.

eztrack (the daharoni fork, v2.x) writes a flat per-frame table with columns
``frame, x, y, detected, distance_px, ...``. CaMAP's behavior loader
(:func:`camap.behavior._load_behavior_xy`) expects a DeepLabCut-style CSV with a
3-row ``scorer / bodyparts / coords`` header, and selects a column by
``(scorer, bodypart, coord)``. This converter bridges the two.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd


def eztrack_to_dlc(
    eztrack_csv: str | Path,
    output_csv: str | Path,
    *,
    bodypart: str = "LED",
    scorer: str = "eztrack",
    frame_col: str = "frame",
    x_col: str = "x",
    y_col: str = "y",
) -> Path:
    """Write a DeepLabCut-format CSV from an eztrack location output.

    Parameters
    ----------
    eztrack_csv:
        Path to the eztrack output CSV (flat columns, e.g. ``Frame, X, Y``).
    output_csv:
        Destination DLC-style CSV path.
    bodypart:
        Bodypart name to write; must match ``behavior.bodypart`` in the CaMAP
        data config.
    scorer:
        Scorer name for the top header row (CaMAP infers it from the header, so
        the exact string is free).
    frame_col, x_col, y_col:
        Column names in the eztrack CSV (the v2.x fork uses ``frame``/``x``/``y``).

    Returns
    -------
    Path
        The path written.
    """
    eztrack_csv = Path(eztrack_csv)
    output_csv = Path(output_csv)

    df = pd.read_csv(eztrack_csv)
    missing = [c for c in (frame_col, x_col, y_col) if c not in df.columns]
    if missing:
        raise ValueError(
            f"eztrack CSV {eztrack_csv.name} missing column(s) {missing}. "
            f"Available: {list(df.columns)}"
        )

    # CaMAP reads the DLC CSV with header=[0,1,2] and takes the first physical
    # column as the frame index. The first column's header triple in a real DLC
    # export is literally ('scorer', 'bodyparts', 'coords').
    out = pd.DataFrame(
        {
            ("scorer", "bodyparts", "coords"): df[frame_col].to_numpy(),
            (scorer, bodypart, "x"): df[x_col].to_numpy(),
            (scorer, bodypart, "y"): df[y_col].to_numpy(),
        }
    )
    out.columns = pd.MultiIndex.from_tuples(out.columns)

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(output_csv, index=False)
    return output_csv
