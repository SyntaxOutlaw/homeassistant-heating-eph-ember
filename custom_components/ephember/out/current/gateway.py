"""Current EMBER API gateway via pyephember2."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any

from ...domain.models import ApiKind, Home, HvacDemand, Zone, ZoneMode
from ...error_handling import EmberApiError, InvalidCredentials
from ...ports.gateway import EmberGateway

_LOGGER = logging.getLogger(__name__)


def _map_current_zone(raw: dict[str, Any], gateway_id: str) -> Zone:
    """Map a pyephember2 zone dict into a domain Zone."""
    from pyephember2.pyephember2 import (
        ZoneMode as PyZoneMode,
        boiler_state,
        zone_advance_active,
        zone_boost_hours,
        zone_boost_timestamp,
        zone_current_temperature,
        zone_is_boost_active,
        zone_is_hotwater,
        zone_mode,
        zone_name,
        zone_target_temperature,
    )

    mode_enum = zone_mode(raw)
    if mode_enum is None:
        mode = ZoneMode.AUTO
    elif isinstance(mode_enum, PyZoneMode):
        mode = ZoneMode(mode_enum.value)
    else:
        mode = ZoneMode(int(mode_enum))

    try:
        current = zone_current_temperature(raw)
    except Exception:  # noqa: BLE001 - library helpers can raise on missing points
        current = None
    try:
        target = zone_target_temperature(raw)
    except Exception:  # noqa: BLE001
        target = None

    boost_active = False
    boost_hours = None
    boost_finish = None
    advance_active = False
    try:
        boost_active = bool(zone_is_boost_active(raw))
        boost_hours = int(zone_boost_hours(raw) or 0)
        if boost_active and boost_hours:
            boost_finish = datetime.fromtimestamp(zone_boost_timestamp(raw), tz=UTC)
    except Exception:  # noqa: BLE001
        pass
    try:
        advance_active = bool(zone_advance_active(raw))
    except Exception:  # noqa: BLE001
        pass

    demand = HvacDemand.UNKNOWN
    if mode == ZoneMode.OFF:
        demand = HvacDemand.OFF
    else:
        try:
            if boiler_state(raw) == 2:
                demand = HvacDemand.HEATING
            else:
                demand = HvacDemand.IDLE
        except Exception:  # noqa: BLE001
            demand = HvacDemand.UNKNOWN

    return Zone(
        zone_id=int(raw["zoneid"]),
        gateway_id=gateway_id,
        name=str(zone_name(raw)),
        mode=mode,
        current_temperature=float(current) if current is not None else None,
        target_temperature=float(target) if target is not None else None,
        is_hot_water=bool(zone_is_hotwater(raw)),
        is_online=True,
        is_boost_active=boost_active,
        is_advance_active=advance_active,
        boost_hours=boost_hours,
        boost_finish=boost_finish,
        prefix=None,
        demand=demand,
        api_kind=ApiKind.CURRENT,
    )


class CurrentGateway(EmberGateway):
    """Adapter around synchronous pyephember2 for newer gateways."""

    def __init__(self, username: str, password: str) -> None:
        self._username = username
        self._password = password
        self._ember: Any | None = None
        self._homes_cache: list[dict[str, Any]] | None = None

    async def login(self) -> None:
        """Create the pyephember2 client (logs in during construction)."""

        def _create() -> Any:
            from pyephember2.pyephember2 import EphEmber

            return EphEmber(self._username, self._password)

        try:
            self._ember = await asyncio.to_thread(_create)
        except RuntimeError as err:
            raise InvalidCredentials(str(err)) from err

    async def list_homes(self) -> list[Home]:
        """List homes via pyephember2."""
        ember = self._require_ember()

        def _list() -> list[dict[str, Any]]:
            return list(ember.list_homes())

        try:
            raw_homes = await asyncio.to_thread(_list)
        except RuntimeError as err:
            raise EmberApiError(str(err)) from err
        self._homes_cache = raw_homes
        homes: list[Home] = []
        for raw in raw_homes:
            homes.append(
                Home(
                    gateway_id=str(raw["gatewayid"]),
                    name=str(raw.get("name") or "Home"),
                    device_type=raw.get("deviceType"),
                    system_type=raw.get("sysTemType"),
                    zone_count=raw.get("zoneCount"),
                    api_kind=ApiKind.AUTO,
                )
            )
        return homes

    async def list_zones(self, gateway_id: str) -> list[Zone]:
        """Fetch zones via homesVT/zoneProgram through pyephember2."""
        ember = self._require_ember()

        def _zones() -> list[dict[str, Any]]:
            # get_home returns zone list for the gateway
            return list(ember.get_home(gateway_id))

        try:
            raw_zones = await asyncio.to_thread(_zones)
        except RuntimeError as err:
            message = str(err)
            if "Error getting zones" in message or "status" in message.lower():
                raise EmberApiError(message, status=1) from err
            raise EmberApiError(message) from err

        # pyephember2 sometimes nests zones under homes; normalize
        if raw_zones and isinstance(raw_zones[0], dict) and "zones" in raw_zones[0]:
            expanded: list[dict[str, Any]] = []
            for home in raw_zones:
                expanded.extend(home.get("zones") or [])
            raw_zones = expanded

        return [_map_current_zone(raw, gateway_id) for raw in raw_zones]

    async def set_mode(self, zone_id: int, mode: ZoneMode) -> None:
        """Set mode through pyephember2."""
        ember = self._require_ember()

        def _set() -> None:
            from pyephember2.pyephember2 import ZoneMode as PyZoneMode

            ember.set_zone_mode(zone_id, PyZoneMode(int(mode)))

        try:
            await asyncio.to_thread(_set)
        except Exception as err:  # noqa: BLE001
            raise EmberApiError(f"Failed to set mode: {err}") from err

    async def set_target_temperature(self, zone_id: int, temperature: float) -> None:
        """Set target temperature through pyephember2."""
        ember = self._require_ember()

        def _set() -> None:
            ember.set_zone_target_temperature(zone_id, temperature)

        try:
            await asyncio.to_thread(_set)
        except Exception as err:  # noqa: BLE001
            raise EmberApiError(f"Failed to set temperature: {err}") from err

    async def boost(self, zone_id: int, hours: int, temperature: float) -> None:
        """Activate boost through pyephember2."""
        ember = self._require_ember()

        def _set() -> None:
            ember.activate_zone_boost(zone_id, temperature, num_hours=hours)

        try:
            await asyncio.to_thread(_set)
        except Exception as err:  # noqa: BLE001
            raise EmberApiError(f"Failed to boost: {err}") from err

    async def cancel_boost(self, zone_id: int) -> None:
        """Cancel boost through pyephember2."""
        ember = self._require_ember()

        def _set() -> None:
            ember.deactivate_zone_boost(zone_id)

        try:
            await asyncio.to_thread(_set)
        except Exception as err:  # noqa: BLE001
            raise EmberApiError(f"Failed to cancel boost: {err}") from err

    async def set_advance(self, zone_id: int, active: bool) -> None:
        """Set schedule advance through pyephember2."""
        ember = self._require_ember()

        def _set() -> None:
            ember.set_zone_advance(zone_id, advance_state=active)

        try:
            await asyncio.to_thread(_set)
        except Exception as err:  # noqa: BLE001
            raise EmberApiError(f"Failed to set advance: {err}") from err

    def _require_ember(self) -> Any:
        if self._ember is None:
            raise InvalidCredentials("Not authenticated with current EMBER API")
        return self._ember
