"""Diagnostic sensors for EPH gateway metadata."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from ...const import DOMAIN
from ...domain.models import Home
from .coordinator import EphEmberDataUpdateCoordinator
from .devices import async_upsert_gateway_device, gateway_device_info


@dataclass(frozen=True, slots=True)
class _GatewayField:
    """One diagnostic field exposed as its own sensor under the gateway device."""

    key: str
    icon: str
    value: Callable[[Home], Any]
    unit: str | None = None
    # When True, skip creating the entity if the home has no value yet.
    optional: bool = False


# Fields shown as separate diagnostic entities (visible under Device info).
_GATEWAY_FIELDS: tuple[_GatewayField, ...] = (
    _GatewayField("invite_code", "mdi:qrcode", lambda h: h.invite_code),
    _GatewayField("weather_location", "mdi:map-marker", lambda h: h.weather_location),
    _GatewayField(
        "holiday_mode",
        "mdi:palm-tree",
        lambda h: _bool_label(h.holiday_mode_active),
    ),
    _GatewayField(
        "frost_protection",
        "mdi:snowflake",
        lambda h: _bool_label(h.frost_protection_enabled),
    ),
    _GatewayField(
        "frost_protection_temperature",
        "mdi:thermometer-low",
        lambda h: h.frost_protection_temperature,
        unit=UnitOfTemperature.CELSIUS,
        optional=True,
    ),
    _GatewayField(
        "quick_boost_temperature",
        "mdi:thermometer-plus",
        lambda h: h.quick_boost_temperature,
        unit=UnitOfTemperature.CELSIUS,
        optional=True,
    ),
    _GatewayField(
        "gateway_datetime",
        "mdi:clock-outline",
        lambda h: h.gateway_datetime,
        optional=True,
    ),
    _GatewayField(
        "utc_time_offset",
        "mdi:earth",
        lambda h: h.utc_time_offset,
        optional=True,
    ),
    _GatewayField("home_id", "mdi:identifier", lambda h: h.home_id, optional=True),
    _GatewayField("zone_count", "mdi:view-grid-outline", lambda h: h.zone_count),
    _GatewayField("api_kind", "mdi:api", lambda h: h.api_kind.value),
    _GatewayField(
        "supports_advance",
        "mdi:skip-forward",
        lambda h: _bool_label(h.supports_advance),
    ),
)


def _bool_label(value: bool | None) -> str | None:
    if value is None:
        return None
    return "on" if value else "off"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up gateway diagnostic sensors."""
    coordinator: EphEmberDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[SensorEntity] = []
    for home in coordinator.service.homes:
        async_upsert_gateway_device(hass, entry, home)
        entities.append(EphEmberGatewaySensor(coordinator, home.gateway_id))
        for field in _GATEWAY_FIELDS:
            if field.optional and field.value(home) is None:
                continue
            entities.append(
                EphEmberGatewayFieldSensor(coordinator, home.gateway_id, field)
            )
    async_add_entities(entities)


class _GatewaySensorBase(
    CoordinatorEntity[EphEmberDataUpdateCoordinator], SensorEntity
):
    """Shared base for gateway diagnostic sensors."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: EphEmberDataUpdateCoordinator,
        gateway_id: str,
    ) -> None:
        super().__init__(coordinator)
        self._gateway_id = gateway_id

    @property
    def home(self) -> Home:
        """Return the current home metadata."""
        return self.coordinator.service.get_home(self._gateway_id)

    @property
    def device_info(self) -> DeviceInfo:
        """Keep Device info fields in sync when home metadata refreshes."""
        return gateway_device_info(self.home)


class EphEmberGatewaySensor(_GatewaySensorBase):
    """Online / offline status for the gateway / timeclock."""

    _attr_translation_key = "gateway"
    _attr_icon = "mdi:router-wireless"

    def __init__(
        self,
        coordinator: EphEmberDataUpdateCoordinator,
        gateway_id: str,
    ) -> None:
        super().__init__(coordinator, gateway_id)
        self._attr_unique_id = f"{gateway_id}_gateway"

    @property
    def native_value(self) -> str | None:
        """Online / offline / unknown."""
        online = self.home.is_online
        if online is None:
            return None
        return "online" if online else "offline"


class EphEmberGatewayFieldSensor(_GatewaySensorBase):
    """Single gateway metadata field as its own diagnostic entity."""

    def __init__(
        self,
        coordinator: EphEmberDataUpdateCoordinator,
        gateway_id: str,
        field: _GatewayField,
    ) -> None:
        super().__init__(coordinator, gateway_id)
        self._field = field
        self._attr_unique_id = f"{gateway_id}_{field.key}"
        self._attr_translation_key = field.key
        self._attr_icon = field.icon
        self._attr_native_unit_of_measurement = field.unit

    @property
    def native_value(self) -> Any:
        """Return the field value from the latest home metadata."""
        return self._field.value(self.home)
