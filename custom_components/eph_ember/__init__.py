"""The EPH Ember integration.

Home Assistant entrypoints are imported lazily so domain/unit tests can import
domain and port modules without installing Home Assistant.
"""

from __future__ import annotations

from typing import Any

try:
    import voluptuous as vol
    from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
    from homeassistant.helpers import config_validation as cv

    from .const import DOMAIN

    # Discovered by hassfest when async_setup is present.
    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Optional(DOMAIN): vol.Schema(
                {
                    vol.Required(CONF_USERNAME): cv.string,
                    vol.Required(CONF_PASSWORD): cv.string,
                }
            )
        },
        extra=vol.ALLOW_EXTRA,
    )
except ImportError:  # pragma: no cover - unit tests without Home Assistant
    CONFIG_SCHEMA = None


async def async_setup(hass: Any, config: dict[str, Any]) -> bool:
    """Set up the EPH Ember integration."""
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
