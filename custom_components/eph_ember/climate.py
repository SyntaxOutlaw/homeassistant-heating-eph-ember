"""Climate platform shim for Home Assistant discovery."""

from .into.ha.climate import async_setup_entry, async_setup_platform

__all__ = ["async_setup_entry", "async_setup_platform"]
