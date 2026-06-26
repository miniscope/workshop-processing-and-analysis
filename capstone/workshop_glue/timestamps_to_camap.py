"""Convert a Miniscope DAQ timestamp CSV into the schema CaMAP reads.

The Miniscope DAQ writes one timestamp file per device with columns
``Frame Number, Time Stamp (ms), Buffer Index`` (one row per frame, the
timestamp being **milliseconds since recording start** on the DAQ's shared
master clock).

CaMAP's loaders expect, by column name:

* neural — a ``timestamp_first`` column (the per-frame neural sample time);
* behavior — a ``frame_index`` column (merge key with the position CSV) and a
  ``unix_time`` column (per-frame time).

and it treats those times as **seconds** (speed thresholds are mm/s, occupancy
is in seconds, shuffle shifts are in seconds). This converter bridges both:
it renames the frame column, converts ms → s, and writes a single CSV carrying
all of ``frame_index, timestamp_first, timestamp_last, unix_time`` so the same
output works whether CaMAP reads it as the neural or the behavior timestamp
(with CaMAP's default column names, so no per-field config is needed).

``unix_time`` here is DAQ-relative seconds, not a true epoch — that's fine:
CaMAP only needs neural and behavior to share one clock, and both DAQ devices
are stamped from the same master clock, so their ms timestamps are directly
comparable once both are divided by 1000.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd


def miniscope_timestamps_to_camap(
    daq_csv: str | Path,
    output_csv: str | Path,
    *,
    frame_col: str = "Frame Number",
    time_ms_col: str = "Time Stamp (ms)",
) -> Path:
    """Write a CaMAP-schema timestamp CSV from a Miniscope DAQ timestamp CSV.

    Parameters
    ----------
    daq_csv:
        Path to a Miniscope DAQ timestamp CSV (``Frame Number``,
        ``Time Stamp (ms)``, ...).
    output_csv:
        Destination CSV path.
    frame_col, time_ms_col:
        Column names in the DAQ CSV for the frame number and the
        millisecond timestamp.

    Returns
    -------
    Path
        The path written, with columns
        ``frame_index, timestamp_first, timestamp_last, unix_time``
        (times in seconds).
    """
    daq_csv = Path(daq_csv)
    output_csv = Path(output_csv)

    df = pd.read_csv(daq_csv)
    missing = [c for c in (frame_col, time_ms_col) if c not in df.columns]
    if missing:
        raise ValueError(
            f"DAQ timestamp CSV {daq_csv.name} missing column(s) {missing}. "
            f"Available: {list(df.columns)}"
        )

    seconds = df[time_ms_col].to_numpy(dtype=float) / 1000.0
    out = pd.DataFrame(
        {
            "frame_index": df[frame_col].to_numpy(),
            "timestamp_first": seconds,
            "timestamp_last": seconds,  # DAQ records one stamp/frame, not a window
            "unix_time": seconds,
        }
    )
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(output_csv, index=False)
    return output_csv
