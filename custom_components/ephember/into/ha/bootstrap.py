"""Composition root helpers loaded by the integration package."""

from __future__ import annotations

import logging

import voluptuous as vol
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.typing import ConfigType

from ...const import DOMAIN
from ...error_handling import EmberApiError, InvalidCredentials
from .coordinator import EphEmberDataUpdateCoordinator
from .dependencies import build_heating_service
from .frontend import async_register_frontend

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.CLIMATE, Platform.SENSOR]

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


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up from YAML if present, then hand off to config entries."""
    hass.data.setdefault(DOMAIN, {})
    await async_register_frontend(hass)

    if DOMAIN in config:
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": SOURCE_IMPORT},
                data=config[DOMAIN],
            )
        )
        ir.async_create_issue(
            hass,
            DOMAIN,
            "deprecated_yaml",
            breaks_in_ha_version="2026.12.0",
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key="deprecated_yaml",
        )

    climate_config = config.get("climate")
    if isinstance(climate_config, list):
        for item in climate_config:
            if not isinstance(item, dict):
                continue
            if item.get("platform") != DOMAIN:
                continue
            hass.async_create_task(
                hass.config_entries.flow.async_init(
                    DOMAIN,
                    context={"source": SOURCE_IMPORT},
                    data={
                        CONF_USERNAME: item[CONF_USERNAME],
                        CONF_PASSWORD: item[CONF_PASSWORD],
                    },
                )
            )
            ir.async_create_issue(
                hass,
                DOMAIN,
                "deprecated_yaml_climate",
                breaks_in_ha_version="2026.12.0",
                is_fixable=False,
                severity=ir.IssueSeverity.WARNING,
                translation_key="deprecated_yaml_climate",
            )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up EPH Controls from a config entry."""
    service = build_heating_service(hass, entry)
    try:
        await service.async_setup()
        await service.async_refresh_zones()
    except InvalidCredentials as err:
        raise ConfigEntryAuthFailed("Invalid EPH Ember credentials") from err
    except EmberApiError as err:
        raise ConfigEntryNotReady(str(err)) from err

    coordinator = EphEmberDataUpdateCoordinator(hass, entry, service)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload when options or credentials change."""
    await hass.config_entries.async_reload(entry.entry_id)
