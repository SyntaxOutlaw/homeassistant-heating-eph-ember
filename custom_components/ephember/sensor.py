"""Sensor platform shim for Home Assistant discovery."""

from .into.ha.sensor import async_setup_entry

__all__ = ["async_setup_entry"]
