"""Inject external deconvolution output (calab: CaTune / CaDecon) into CaMAP.

In this workshop, deconvolution is an explicit middle stage: Minian's denoised
traces are deconvolved by CaTune or CaDecon (both in ``calab``) into a per-unit
estimate of neural activity, saved as ``deconv_out/activity.npy`` (shape
``(n_cells, n_frames)``, float). CaMAP normally runs its own OASIS deconvolution
in ``ds.deconvolve()``, which populates ``ds.good_unit_ids`` and ``ds.S_list``
for ``match_events()`` to consume. To use the external deconvolution instead, we
skip ``deconvolve()`` and set those two attributes directly.

The activity rows are aligned 1:1, in order, with the Minian ``C`` traces that
were fed to calab — i.e. the same order as ``ds.traces``'s ``unit_id`` axis.
So the unit ids come from ``ds.traces`` (the ``.npy`` itself carries no ids).

Contract enforced by CaMAP (``camap.dataset.arena.match_events``):
  * ``ds.S_list[i]`` is the 1-D activity trace for unit ``ds.good_unit_ids[i]``.
  * each activity trace length must equal the number of neural frames.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np


def inject_deconv_activity(ds: Any, deconv_output: str | Path) -> None:
    """Load the deconvolved neural activity and inject it into ``ds`` (no OASIS).

    Call after ``ds.load()`` (so ``ds.traces`` is available for unit-id
    alignment) and before ``ds.match_events()``; do **not** call
    ``ds.deconvolve()``.

    Parameters
    ----------
    ds:
        A loaded CaMAP dataset (``ds.traces`` populated).
    deconv_output:
        Path to the deconvolved activity ``.npy``, or the ``deconv_out/``
        directory containing it (calab: CaTune / CaDecon).
    """
    if ds.traces is None:
        raise RuntimeError(
            "Call ds.load() before injecting — ds.traces is needed to align "
            "activity rows with unit ids."
        )

    activity_path = _resolve_activity_npy(Path(deconv_output))
    activity = np.load(activity_path)
    if activity.ndim == 1:
        activity = activity.reshape(1, -1)

    unit_ids = [int(u) for u in ds.traces.coords["unit_id"].values]
    n_units = len(unit_ids)
    n_frames = int(ds.traces.sizes["frame"])

    if activity.shape[0] != n_units:
        raise ValueError(
            f"Deconvolved activity has {activity.shape[0]} rows but ds.traces has "
            f"{n_units} units. Rows must align 1:1 (in order) with the Minian C "
            f"traces fed to calab — re-run deconvolution on the same traces."
        )
    if activity.shape[1] != n_frames:
        raise ValueError(
            f"Deconvolved activity has {activity.shape[1]} timepoints but there are "
            f"{n_frames} neural frames."
        )

    ds.good_unit_ids = unit_ids
    ds.S_list = [np.asarray(activity[i], dtype=float) for i in range(n_units)]


def _resolve_activity_npy(path: Path) -> Path:
    """Find the deconvolved-activity ``.npy`` at *path* (file or directory)."""
    if path.is_file():
        return path
    if path.is_dir():
        preferred = path / "activity.npy"
        if preferred.exists():
            return preferred
        hits = sorted(path.glob("*activity*.npy"))
        if hits:
            return hits[0]
    raise FileNotFoundError(
        f"No deconvolved activity .npy found at {path}. Produce one with "
        f"tutorials/deconvolution/run_catune.py or run_cadecon.py, or fetch the "
        f"deconv_out bundle (python scripts/get_data.py)."
    )
