"""Glue between the upstream workshop tools and CaMAP."""

from workshop_glue.deconv_inject import inject_deconv_activity
from workshop_glue.eztrack_to_dlc import eztrack_to_dlc

__all__ = ["eztrack_to_dlc", "inject_deconv_activity"]
