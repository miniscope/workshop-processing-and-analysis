"""Inject CaTune deconvolution output into a CaMAP dataset.

CaMAP normally runs its own OASIS deconvolution in ``ds.deconvolve()``, which
populates ``ds.good_unit_ids`` and ``ds.S_list`` for ``match_events()`` to
consume. To use CaTune's deconvolution instead, we skip ``deconvolve()`` and set
those two attributes directly.

Contract enforced by CaMAP (``camap.dataset.arena.match_events``):
  * ``ds.S_list[i]`` is the 1-D spike train for unit ``ds.good_unit_ids[i]``
    (order matters — the two lists are zipped).
  * each spike train length must equal the number of neural timestamps.

The CaTune output *parser* is a TODO pending the CaMAP CaTune-integration dev
branch; only the injection mechanics + validation are final here.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np


def inject_catune_spikes(
    ds: Any,
    catune_output: str | Path,
) -> None:
    """Load CaTune spikes and inject them into ``ds`` in place of OASIS.

    Call after ``ds.load()`` and before ``ds.match_events()``; do **not** call
    ``ds.deconvolve()``.

    Parameters
    ----------
    ds:
        A loaded CaMAP dataset (``ds.traces`` populated).
    catune_output:
        Path to the CaTune deconvolution output.
    """
    catune_output = Path(catune_output)

    unit_ids, s_list = _parse_catune_output(catune_output)

    if len(unit_ids) != len(s_list):
        raise ValueError(
            f"unit_ids ({len(unit_ids)}) and spike trains ({len(s_list)}) "
            "must have the same length."
        )
    if ds.traces is not None:
        n_frames = ds.traces.sizes["frame"]
        bad = [(u, len(s)) for u, s in zip(unit_ids, s_list) if len(s) != n_frames]
        if bad:
            raise ValueError(
                f"CaTune spike trains must match the neural frame count ({n_frames}). "
                f"Mismatched units (unit_id, length): {bad[:5]}{' ...' if len(bad) > 5 else ''}"
            )

    ds.good_unit_ids = [int(u) for u in unit_ids]
    ds.S_list = [np.asarray(s, dtype=float) for s in s_list]


def _parse_catune_output(path: Path) -> tuple[list[int], list[np.ndarray]]:
    """Parse the CaTune output into ``(unit_ids, spike_trains)``.

    TODO: implement against the CaTune dev-branch format. Likely a zarr/npz with
    a spikes array shaped ``(unit, frame)`` plus a ``unit_id`` coordinate. Until
    then this raises so the failure is loud rather than silent.
    """
    raise NotImplementedError(
        "CaTune output parsing not implemented yet — wire this up against the "
        f"CaTune dev-branch format once available (input was: {path})."
    )
