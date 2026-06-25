"""Inject external deconvolution output (calab: CaTune / CaDecon) into CaMAP.

In this workshop, deconvolution is an explicit middle stage: Minian traces are
deconvolved by CaTune or CaDecon (both in ``calab``) into a per-unit estimate of
neural activity, and the result is fed to CaMAP. CaMAP normally runs its own
OASIS deconvolution in ``ds.deconvolve()``, which populates ``ds.good_unit_ids``
and ``ds.S_list`` for ``match_events()`` to consume. To use the external
deconvolution instead, we skip ``deconvolve()`` and set those two attributes
directly.

Contract enforced by CaMAP (``camap.dataset.arena.match_events``):
  * ``ds.S_list[i]`` is the 1-D deconvolved activity trace for unit
    ``ds.good_unit_ids[i]`` (order matters — the two lists are zipped).
  * each activity trace length must equal the number of neural timestamps.

The calab output *parser* is a TODO pending the calab/CaMAP integration dev
branch; only the injection mechanics + validation are final here.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np


def inject_deconv_activity(
    ds: Any,
    deconv_output: str | Path,
) -> None:
    """Load the deconvolved neural activity and inject it into ``ds`` (no OASIS).

    Call after ``ds.load()`` and before ``ds.match_events()``; do **not** call
    ``ds.deconvolve()``.

    Parameters
    ----------
    ds:
        A loaded CaMAP dataset (``ds.traces`` populated).
    deconv_output:
        Path to the deconvolution output (calab: CaTune / CaDecon) — a per-unit
        estimate of neural activity.
    """
    deconv_output = Path(deconv_output)

    unit_ids, activity_traces = _parse_deconv_output(deconv_output)

    if len(unit_ids) != len(activity_traces):
        raise ValueError(
            f"unit_ids ({len(unit_ids)}) and activity traces ({len(activity_traces)}) "
            "must have the same length."
        )
    if ds.traces is not None:
        n_frames = ds.traces.sizes["frame"]
        bad = [(u, len(a)) for u, a in zip(unit_ids, activity_traces) if len(a) != n_frames]
        if bad:
            raise ValueError(
                f"Deconvolved activity traces must match the neural frame count ({n_frames}). "
                f"Mismatched units (unit_id, length): {bad[:5]}{' ...' if len(bad) > 5 else ''}"
            )

    ds.good_unit_ids = [int(u) for u in unit_ids]
    ds.S_list = [np.asarray(a, dtype=float) for a in activity_traces]


def _parse_deconv_output(path: Path) -> tuple[list[int], list[np.ndarray]]:
    """Parse the calab (CaTune / CaDecon) output into ``(unit_ids, activity_traces)``.

    TODO: implement against the calab dev-branch format. Likely a zarr/npz with a
    deconvolved-activity array shaped ``(unit, frame)`` plus a ``unit_id``
    coordinate. Until then this raises so the failure is loud rather than silent.
    """
    raise NotImplementedError(
        "calab (CaTune/CaDecon) output parsing not implemented yet — wire this "
        f"up against the dev-branch format once available (input was: {path})."
    )
