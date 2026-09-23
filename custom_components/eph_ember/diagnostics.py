"""Diagnostics shim for Home Assistant discovery."""

from .into.ha.diagnostics import async_get_config_entry_diagnostics

__all__ = ["async_get_config_entry_diagnostics"]
