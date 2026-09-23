"""Shared Home Assistant device helpers for EPH Controls."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo

from ...const import DOMAIN, MANUFACTURER
from ...domain.models import Home


def gateway_device_info(home: Home) -> DeviceInfo:
    """Build DeviceInfo for a gateway from enriched Home data."""
    model = home.system_type or home.hardware_label or "EPH Gateway"
    model_id = None
    if home.device_type is not None:
        model_id = str(home.device_type)
    hw_version = home.hardware_label
    if home.hardware_label and home.system_type and home.hardware_label != home.system_type:
        hw_version = home.hardware_label
    elif home.device_type is not None and home.hardware_label is None:
        hw_version = f"deviceType {home.device_type}"

    return DeviceInfo(
        identifiers={(DOMAIN, home.gateway_id)},
        manufacturer=MANUFACTURER,
        name=home.name,
        model=model,
        model_id=model_id,
        serial_number=home.gateway_id,
        hw_version=hw_version,
    )


def async_upsert_gateway_device(
    hass: HomeAssistant,
    entry: ConfigEntry,
    home: Home,
) -> None:
    """Create or refresh the gateway device registry entry."""
    info = gateway_device_info(home)
    registry = dr.async_get(hass)
    device = registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers=info["identifiers"],
        manufacturer=info.get("manufacturer"),
        name=info.get("name"),
        model=info.get("model"),
        model_id=info.get("model_id"),
        serial_number=info.get("serial_number"),
        hw_version=info.get("hw_version"),
    )
    # Clear any previously stuffed firmware/software string.
    if device.sw_version is not None:
        registry.async_update_device(device.id, sw_version=None)
