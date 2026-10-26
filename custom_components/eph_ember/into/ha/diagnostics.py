"""Diagnostics support for EPH Controls."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from ...const import DOMAIN
from .coordinator import EphEmberDataUpdateCoordinator
from .dependencies import TO_REDACT


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator: EphEmberDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    homes = [
        {
            "gateway_id": home.gateway_id,
            "name": home.name,
            "device_type": home.device_type,
            "system_type": home.system_type,
            "zone_count": home.zone_count,
            "api_kind": home.api_kind.value,
            "home_id": home.home_id,
            "is_online": home.is_online,
            "weather_location": home.weather_location,
            "holiday_mode_active": home.holiday_mode_active,
            "frost_protection_enabled": home.frost_protection_enabled,
            "supports_advance": home.supports_advance,
            "hardware": home.hardware_label,
        }
        for home in coordinator.service.homes
    ]
    zones = [
        {
            "zone_id": zone.zone_id,
            "gateway_id": zone.gateway_id,
            "name": zone.name,
            "mode": int(zone.mode),
            "is_hot_water": zone.is_hot_water,
            "is_online": zone.is_online,
            "is_boost_active": zone.is_boost_active,
            "api_kind": zone.api_kind.value,
            "has_current_temperature": zone.current_temperature is not None,
            "has_target_temperature": zone.target_temperature is not None,
            "prefix": zone.prefix,
            "demand": zone.demand.value,
        }
        for zone in coordinator.service.zones
    ]
    return async_redact_data(
        {
            "entry": {
                "title": entry.title,
                "data": dict(entry.data),
                "options": dict(entry.options),
            },
            "homes": homes,
            "zones": zones,
        },
        TO_REDACT,
    )
