"""The EPH Controls integration.

Home Assistant entrypoints are imported lazily so domain/unit tests can import
domain and port modules without installing Home Assistant.
"""

from __future__ import annotations

from typing import Any


async def async_setup(hass: Any, config: dict[str, Any]) -> bool:
    """Set up the EPH Controls integration."""
    from .into.ha.bootstrap import async_setup as _async_setup

    return await _async_setup(hass, config)


async def async_setup_entry(hass: Any, entry: Any) -> bool:
    """Set up a config entry."""
    from .into.ha.bootstrap import async_setup_entry as _async_setup_entry

    return await _async_setup_entry(hass, entry)


async def async_unload_entry(hass: Any, entry: Any) -> bool:
    """Unload a config entry."""
    from .into.ha.bootstrap import async_unload_entry as _async_unload_entry

    return await _async_unload_entry(hass, entry)


async def async_reload_entry(hass: Any, entry: Any) -> None:
    """Reload a config entry."""
    from .into.ha.bootstrap import async_reload_entry as _async_reload_entry

    await _async_reload_entry(hass, entry)
