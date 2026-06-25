"""Glue between the upstream workshop tools and CaMAP."""

from workshop_glue.catune_inject import inject_catune_spikes
from workshop_glue.eztrack_to_dlc import eztrack_to_dlc

__all__ = ["eztrack_to_dlc", "inject_catune_spikes"]
