"""Heating orchestration service."""

from __future__ import annotations

import logging

from ..error_handling import EmberApiError, ZoneNotFound
from ..ports.gateway import EmberGateway
from .models import ApiKind, Home, Zone, ZoneMode

_LOGGER = logging.getLogger(__name__)


def detect_api_kind(home: Home, override: ApiKind = ApiKind.AUTO) -> ApiKind:
    """Choose legacy vs current API for a home."""
    if override != ApiKind.AUTO:
        return override
    if home.device_type == 1 or home.system_type == "EMBER-PS":
        return ApiKind.LEGACY
    return ApiKind.CURRENT


class HeatingService:
    """
    Domain service for EMBER heating accounts.

    Takes gateway ports via constructor injection. Chooses legacy or current
    per home and keeps the last polled zone map.
    """

    def __init__(
        self,
        legacy: EmberGateway,
        current: EmberGateway,
        api_version: ApiKind = ApiKind.AUTO,
    ) -> None:
        self._legacy = legacy
        self._current = current
        self._api_version = api_version
        self._homes: list[Home] = []
        self._zones_by_id: dict[int, Zone] = {}
        self._gateway_for_home: dict[str, EmberGateway] = {}
        self._api_kind_for_home: dict[str, ApiKind] = {}
        self._logged_in_current = False

    @property
    def homes(self) -> list[Home]:
        """Homes discovered for this account."""
        return list(self._homes)

    @property
    def zones(self) -> list[Zone]:
        """Last polled zones across all homes."""
        return list(self._zones_by_id.values())

    def get_zone(self, zone_id: int) -> Zone:
        """Return a zone from the last poll."""
        try:
            return self._zones_by_id[zone_id]
        except KeyError as err:
            raise ZoneNotFound(f"Unknown zone id {zone_id}") from err

    async def async_setup(self) -> list[Home]:
        """Authenticate, list homes, and bind each home to a gateway."""
        await self._legacy.login()
        raw_homes = await self._legacy.list_homes()
        homes: list[Home] = []
        for home in raw_homes:
            kind = detect_api_kind(home, self._api_version)
            bound = Home(
                gateway_id=home.gateway_id,
                name=home.name,
                device_type=home.device_type,
                system_type=home.system_type,
                zone_count=home.zone_count,
                api_kind=kind,
            )
            gateway = await self._gateway_for_kind(kind)
            self._gateway_for_home[bound.gateway_id] = gateway
            self._api_kind_for_home[bound.gateway_id] = kind
            homes.append(bound)
            _LOGGER.debug(
                "Home %s (%s) using %s API",
                bound.name,
                bound.gateway_id,
                kind.value,
            )
        self._homes = homes
        return homes

    async def async_refresh_zones(self) -> list[Zone]:
        """Poll every home and replace the zone cache."""
        if not self._homes:
            await self.async_setup()

        zones: dict[int, Zone] = {}
        for home in self._homes:
            home_zones = await self._list_zones_with_fallback(home)
            for zone in home_zones:
                zones[zone.zone_id] = zone
        self._zones_by_id = zones
        return self.zones

    async def async_set_mode(self, zone_id: int, mode: ZoneMode) -> None:
        """Set mode for a zone and refresh that zone's gateway."""
        zone = self.get_zone(zone_id)
        await self._gateway_for_home[zone.gateway_id].set_mode(zone_id, mode)
        await self._refresh_home(zone.gateway_id)

    async def async_set_target_temperature(self, zone_id: int, temperature: float) -> None:
        """Set target temperature for a zone."""
        zone = self.get_zone(zone_id)
        await self._gateway_for_home[zone.gateway_id].set_target_temperature(
            zone_id, temperature
        )
        await self._refresh_home(zone.gateway_id)

    async def async_boost(self, zone_id: int, hours: int, temperature: float) -> None:
        """Activate boost for a zone."""
        zone = self.get_zone(zone_id)
        await self._gateway_for_home[zone.gateway_id].boost(zone_id, hours, temperature)
        await self._refresh_home(zone.gateway_id)

    async def async_cancel_boost(self, zone_id: int) -> None:
        """Cancel boost for a zone."""
        zone = self.get_zone(zone_id)
        await self._gateway_for_home[zone.gateway_id].cancel_boost(zone_id)
        await self._refresh_home(zone.gateway_id)

    async def async_set_advance(self, zone_id: int, active: bool) -> None:
        """Enable or cancel schedule advance for a zone."""
        zone = self.get_zone(zone_id)
        await self._gateway_for_home[zone.gateway_id].set_advance(zone_id, active)
        await self._refresh_home(zone.gateway_id)

    async def _gateway_for_kind(self, kind: ApiKind) -> EmberGateway:
        if kind == ApiKind.LEGACY:
            return self._legacy
        if not self._logged_in_current:
            await self._current.login()
            self._logged_in_current = True
        return self._current

    async def _list_zones_with_fallback(self, home: Home) -> list[Zone]:
        gateway = self._gateway_for_home[home.gateway_id]
        kind = self._api_kind_for_home[home.gateway_id]
        try:
            return await gateway.list_zones(home.gateway_id)
        except EmberApiError as err:
            if kind != ApiKind.CURRENT or self._api_version != ApiKind.AUTO:
                raise
            _LOGGER.warning(
                "Current API failed for gateway %s (%s); falling back to legacy polling",
                home.gateway_id,
                err,
            )
            self._gateway_for_home[home.gateway_id] = self._legacy
            self._api_kind_for_home[home.gateway_id] = ApiKind.LEGACY
            home_index = next(
                i for i, item in enumerate(self._homes) if item.gateway_id == home.gateway_id
            )
            self._homes[home_index] = Home(
                gateway_id=home.gateway_id,
                name=home.name,
                device_type=home.device_type,
                system_type=home.system_type,
                zone_count=home.zone_count,
                api_kind=ApiKind.LEGACY,
            )
            return await self._legacy.list_zones(home.gateway_id)

    async def _refresh_home(self, gateway_id: str) -> None:
        home = next(item for item in self._homes if item.gateway_id == gateway_id)
        for zone in await self._list_zones_with_fallback(home):
            self._zones_by_id[zone.zone_id] = zone
