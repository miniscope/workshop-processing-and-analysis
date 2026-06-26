"""Glue between the upstream workshop tools and CaMAP."""

from workshop_glue.deconv_inject import inject_deconv_activity
from workshop_glue.eztrack_to_camap import eztrack_to_camap
from workshop_glue.timestamps_to_camap import miniscope_timestamps_to_camap

__all__ = [
    "eztrack_to_camap",
    "inject_deconv_activity",
    "miniscope_timestamps_to_camap",
]
