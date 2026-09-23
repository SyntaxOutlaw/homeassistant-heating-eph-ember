"""Climate platform for EPH Controls."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, CONF_PASSWORD, CONF_USERNAME, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_platform
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from ...const import (
    ATTR_BOOST_ACTIVE,
    ATTR_BOOST_FINISH,
    ATTR_BOOST_HOURS,
    ATTR_GATEWAY_ID,
    ATTR_IS_ONLINE,
    ATTR_PREFIX,
    ATTR_TEMPERATURE_AVAILABLE,
    ATTR_ZONE_ID,
    DEFAULT_BOOST_HOURS,
    DEFAULT_BOOST_TEMP,
    DEFAULT_HOT_WATER_BOOST_TEMP,
    DOMAIN,
    MAX_TEMP,
    MIN_TEMP,
    PRESET_ALL_DAY,
    SERVICE_BOOST_ZONE,
    SERVICE_CANCEL_BOOST,
    TEMP_STEP,
)
from ...domain.models import ApiKind, Home, HvacDemand, Zone, ZoneMode
from ...error_handling import EmberApiError
from .coordinator import EphEmberDataUpdateCoordinator
from .devices import gateway_device_info

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Import legacy YAML climate platform config into a config entry."""
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data={
                CONF_USERNAME: config[CONF_USERNAME],
                CONF_PASSWORD: config[CONF_PASSWORD],
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


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up climate entities from a config entry."""
    coordinator: EphEmberDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities = [
        EphEmberClimate(coordinator, zone, coordinator.service.get_home(zone.gateway_id))
        for zone in coordinator.data.values()
    ]
    async_add_entities(entities)

    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_BOOST_ZONE,
        {
            vol.Required("hours"): vol.All(vol.Coerce(int), vol.Range(min=1, max=3)),
            vol.Optional("temperature"): vol.Coerce(float),
        },
        "async_boost_zone",
    )
    platform.async_register_entity_service(
        SERVICE_CANCEL_BOOST,
        {},
        "async_cancel_boost",
    )


class EphEmberClimate(CoordinatorEntity[EphEmberDataUpdateCoordinator], ClimateEntity):
    """Representation of an EPH Ember zone as a climate entity."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    # HEAT is labeled "Boost"; HEAT_COOL is labeled "Advance" (current API only).
    _attr_preset_modes = [PRESET_ALL_DAY]
    _attr_translation_key = "zone"

    def __init__(
        self,
        coordinator: EphEmberDataUpdateCoordinator,
        zone: Zone,
        home: Home,
    ) -> None:
        """Initialize the climate entity."""
        super().__init__(coordinator)
        self._zone_id = zone.zone_id
        self._gateway_id = zone.gateway_id
        self._attr_unique_id = f"{zone.gateway_id}_{zone.zone_id}"
        self._attr_name = zone.name
        self._apply_zone(zone)

    @property
    def home(self) -> Home:
        """Return gateway metadata for this zone."""
        return self.coordinator.service.get_home(self._gateway_id)

    @property
    def device_info(self):
        """Attach zones to the gateway device; refresh Device info fields."""
        return gateway_device_info(self.home)

    @property
    def hvac_modes(self) -> list[HVACMode]:
        """Return modes; omit Advance on legacy gateways."""
        modes = [HVACMode.AUTO, HVACMode.HEAT, HVACMode.OFF]
        if self.home.supports_advance:
            modes.insert(2, HVACMode.HEAT_COOL)
        return modes

    @property
    def zone(self) -> Zone:
        """Return the current zone from coordinator data."""
        return self.coordinator.data[self._zone_id]

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if self._zone_id not in self.coordinator.data:
            return
        self._apply_zone(self.zone)
        super()._handle_coordinator_update()

    def _apply_zone(self, zone: Zone) -> None:
        """Update cached attributes from a zone."""
        features = (
            ClimateEntityFeature.TURN_ON
            | ClimateEntityFeature.TURN_OFF
            | ClimateEntityFeature.PRESET_MODE
        )
        if not zone.is_hot_water:
            features |= ClimateEntityFeature.TARGET_TEMPERATURE
            self._attr_target_temperature_step = TEMP_STEP
            self._attr_min_temp = MIN_TEMP
            self._attr_max_temp = MAX_TEMP
        else:
            self._attr_target_temperature_step = None
            if zone.target_temperature is not None:
                self._attr_min_temp = zone.target_temperature
                self._attr_max_temp = zone.target_temperature
        self._attr_supported_features = features

    def _boost_temperature(self) -> float:
        """Target temperature to send with a boost command."""
        zone = self.zone
        if zone.target_temperature is not None:
            return float(zone.target_temperature)
        if zone.is_hot_water:
            return DEFAULT_HOT_WATER_BOOST_TEMP
        return DEFAULT_BOOST_TEMP

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        return self.zone.current_temperature

    @property
    def target_temperature(self) -> float | None:
        """Return the target temperature."""
        return self.zone.target_temperature

    @property
    def hvac_mode(self) -> HVACMode:
        """Return Boost / Advance / Auto / Off."""
        zone = self.zone
        if zone.is_boost_active:
            return HVACMode.HEAT
        if zone.is_advance_active:
            return HVACMode.HEAT_COOL
        if zone.mode == ZoneMode.OFF:
            return HVACMode.OFF
        return HVACMode.AUTO

    @property
    def preset_mode(self) -> str | None:
        """Return all_day when that EPH mode is active."""
        if self.zone.mode == ZoneMode.ALL_DAY and not self.zone.is_boost_active:
            return PRESET_ALL_DAY
        return None

    @property
    def hvac_action(self) -> HVACAction | None:
        """Return current HVAC action."""
        demand = self.zone.demand
        if demand == HvacDemand.OFF:
            return HVACAction.OFF
        if demand == HvacDemand.HEATING:
            return HVACAction.HEATING
        if demand == HvacDemand.IDLE:
            return HVACAction.IDLE
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return zone attributes."""
        zone = self.zone
        return {
            ATTR_ZONE_ID: zone.zone_id,
            ATTR_GATEWAY_ID: zone.gateway_id,
            ATTR_IS_ONLINE: zone.is_online,
            ATTR_TEMPERATURE_AVAILABLE: zone.current_temperature is not None,
            ATTR_BOOST_ACTIVE: zone.is_boost_active,
            ATTR_BOOST_HOURS: zone.boost_hours,
            ATTR_BOOST_FINISH: zone.boost_finish.isoformat() if zone.boost_finish else None,
            ATTR_PREFIX: zone.prefix,
            "advance_active": zone.is_advance_active,
        }

    async def _async_clear_overrides(self) -> None:
        """Cancel boost and advance before switching to a run mode."""
        zone = self.zone
        if zone.is_boost_active:
            await self.coordinator.service.async_cancel_boost(self._zone_id)
        if zone.is_advance_active:
            try:
                await self.coordinator.service.async_set_advance(self._zone_id, False)
            except EmberApiError as err:
                _LOGGER.warning(
                    "Could not cancel advance via cloud for zone %s: %s",
                    self._zone_id,
                    err,
                )

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set Auto/Off, or activate Boost / Advance."""
        if hvac_mode == HVACMode.HEAT:
            await self.coordinator.service.async_boost(
                self._zone_id, DEFAULT_BOOST_HOURS, self._boost_temperature()
            )
            await self.coordinator.async_request_refresh()
            return
        if hvac_mode == HVACMode.HEAT_COOL:
            if not self.home.supports_advance:
                _LOGGER.error("Advance is not supported on this gateway")
                return
            await self.coordinator.service.async_set_advance(self._zone_id, True)
            await self.coordinator.async_request_refresh()
            return
        if hvac_mode == HVACMode.OFF:
            await self._async_clear_overrides()
            await self.coordinator.service.async_set_mode(self._zone_id, ZoneMode.OFF)
            await self.coordinator.async_request_refresh()
            return
        if hvac_mode == HVACMode.AUTO:
            await self._async_clear_overrides()
            await self.coordinator.service.async_set_mode(self._zone_id, ZoneMode.AUTO)
            await self.coordinator.async_request_refresh()
            return
        _LOGGER.error("Unsupported HVAC mode %s", hvac_mode)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set all-day preset."""
        if preset_mode != PRESET_ALL_DAY:
            _LOGGER.error("Unsupported preset %s", preset_mode)
            return
        await self._async_clear_overrides()
        await self.coordinator.service.async_set_mode(self._zone_id, ZoneMode.ALL_DAY)
        await self.coordinator.async_request_refresh()

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None or self.zone.is_hot_water:
            return
        await self.coordinator.service.async_set_target_temperature(
            self._zone_id, float(temperature)
        )
        await self.coordinator.async_request_refresh()

    async def async_boost_zone(self, hours: int, temperature: float | None = None) -> None:
        """Service handler to boost this zone."""
        target = temperature if temperature is not None else self._boost_temperature()
        await self.coordinator.service.async_boost(self._zone_id, hours, float(target))
        await self.coordinator.async_request_refresh()

    async def async_cancel_boost(self) -> None:
        """Service handler to cancel boost."""
        await self.coordinator.service.async_cancel_boost(self._zone_id)
        await self.coordinator.async_request_refresh()
