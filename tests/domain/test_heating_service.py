"""Unit tests for domain models and HeatingService."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest

from custom_components.ephember.domain.heating_service import HeatingService, detect_api_kind
from custom_components.ephember.domain.models import ApiKind, Home, HvacDemand, Zone, ZoneMode
from custom_components.ephember.error_handling import EmberApiError, ZoneNotFound
from custom_components.ephember.out.legacy.gateway import (
    demand_from_legacy_zone,
    normalize_temperature,
    zone_from_polling,
)


def _home(**overrides: Any) -> Home:
    data = {
        "gateway_id": "gw1",
        "name": "Home",
        "device_type": 1,
        "system_type": "EMBER-PS",
        "zone_count": 3,
        "api_kind": ApiKind.AUTO,
    }
    data.update(overrides)
    return Home(**data)


def _zone(**overrides: Any) -> Zone:
    data = {
        "zone_id": 105625,
        "gateway_id": "gw1",
        "name": "Downstairs",
        "mode": ZoneMode.OFF,
        "current_temperature": None,
        "target_temperature": None,
        "is_hot_water": False,
        "is_online": False,
        "is_boost_active": False,
        "is_advance_active": False,
        "boost_hours": None,
        "boost_finish": None,
        "prefix": "This zone is in OFF mode",
        "demand": HvacDemand.OFF,
        "api_kind": ApiKind.LEGACY,
    }
    data.update(overrides)
    return Zone(**data)


class FakeGateway:
    """Minimal EmberGateway double."""

    def __init__(self, homes: list[Home] | None = None, zones: list[Zone] | None = None) -> None:
        self.homes = homes or []
        self.zones = zones or []
        self.login = AsyncMock()
        self.set_mode = AsyncMock()
        self.set_target_temperature = AsyncMock()
        self.boost = AsyncMock()
        self.cancel_boost = AsyncMock()
        self.set_advance = AsyncMock()
        self.list_homes = AsyncMock(side_effect=lambda: list(self.homes))
        self.list_zones = AsyncMock(side_effect=lambda gateway_id: [z for z in self.zones if z.gateway_id == gateway_id])


def test_detect_api_kind_legacy() -> None:
    assert detect_api_kind(_home()) == ApiKind.LEGACY
    assert detect_api_kind(_home(device_type=4, system_type="EMBER-PS")) == ApiKind.LEGACY


def test_detect_api_kind_current() -> None:
    assert detect_api_kind(_home(device_type=4, system_type="OTHER")) == ApiKind.CURRENT


def test_detect_api_kind_override() -> None:
    assert detect_api_kind(_home(), ApiKind.CURRENT) == ApiKind.CURRENT
    assert detect_api_kind(_home(device_type=4, system_type="X"), ApiKind.LEGACY) == ApiKind.LEGACY


def test_normalize_temperature_sentinel() -> None:
    assert normalize_temperature(-300) is None
    assert normalize_temperature(-300.0) is None
    assert normalize_temperature(21.5) == 21.5
    assert normalize_temperature(None) is None


def test_demand_from_legacy_prefix() -> None:
    assert demand_from_legacy_zone({"prefix": "This zone is in OFF mode"}, ZoneMode.OFF) == HvacDemand.OFF
    assert (
        demand_from_legacy_zone({"prefix": "This zone is off until 07:20"}, ZoneMode.AUTO)
        == HvacDemand.IDLE
    )
    assert (
        demand_from_legacy_zone({"prefix": "This zone is active until 10:00"}, ZoneMode.AUTO)
        == HvacDemand.HEATING
    )
    assert (
        demand_from_legacy_zone({"prefix": None, "isboostactive": True}, ZoneMode.AUTO)
        == HvacDemand.HEATING
    )


def test_zone_from_polling_maps_fields() -> None:
    raw = {
        "zoneid": 105625,
        "name": "Downstairs",
        "mode": 3,
        "currenttemperature": -300.0,
        "targettemperature": -300.0,
        "ishotwater": False,
        "isonline": False,
        "isboostactive": False,
        "isadvanceactive": False,
        "prefix": "This zone is in OFF mode",
        "boostActivations": None,
    }
    zone = zone_from_polling(raw, "3890845148")
    assert zone.zone_id == 105625
    assert zone.mode == ZoneMode.OFF
    assert zone.current_temperature is None
    assert zone.target_temperature is None
    assert zone.is_hot_water is False
    assert zone.demand == HvacDemand.OFF
    assert zone.api_kind == ApiKind.LEGACY


def test_zone_from_polling_falls_back_to_stored_target() -> None:
    raw = {
        "zoneid": 1,
        "name": "Hall",
        "mode": 0,
        "currenttemperature": -300.0,
        "targettemperature": -300.0,
        "storedtargettemperature": 19.5,
        "ishotwater": False,
        "isonline": False,
        "isboostactive": False,
        "isadvanceactive": False,
        "prefix": "This zone is off until 07:20",
    }
    zone = zone_from_polling(raw, "gw")
    assert zone.current_temperature is None
    assert zone.target_temperature == 19.5



@pytest.mark.asyncio
async def test_heating_service_selects_legacy() -> None:
    home = _home()
    zone = _zone()
    legacy = FakeGateway(homes=[home], zones=[zone])
    current = FakeGateway()
    service = HeatingService(legacy=legacy, current=current, api_version=ApiKind.AUTO)

    homes = await service.async_setup()
    assert homes[0].api_kind == ApiKind.LEGACY
    legacy.login.assert_awaited()
    current.login.assert_not_awaited()

    zones = await service.async_refresh_zones()
    assert zones[0].name == "Downstairs"
    legacy.list_zones.assert_awaited_with("gw1")


@pytest.mark.asyncio
async def test_heating_service_falls_back_to_legacy() -> None:
    home = _home(device_type=4, system_type="NEW")
    zone = _zone(api_kind=ApiKind.LEGACY)
    legacy = FakeGateway(homes=[home], zones=[zone])
    current = FakeGateway(homes=[home], zones=[])
    current.list_zones = AsyncMock(side_effect=EmberApiError("Service internal exception", status=1))
    service = HeatingService(legacy=legacy, current=current, api_version=ApiKind.AUTO)

    await service.async_setup()
    assert service.homes[0].api_kind == ApiKind.CURRENT
    current.login.assert_awaited()

    zones = await service.async_refresh_zones()
    assert len(zones) == 1
    assert service.homes[0].api_kind == ApiKind.LEGACY
    legacy.list_zones.assert_awaited()


@pytest.mark.asyncio
async def test_heating_service_commands() -> None:
    home = _home()
    zone = _zone()
    legacy = FakeGateway(homes=[home], zones=[zone])
    service = HeatingService(legacy=legacy, current=FakeGateway(), api_version=ApiKind.LEGACY)
    await service.async_setup()
    await service.async_refresh_zones()

    await service.async_set_mode(105625, ZoneMode.AUTO)
    legacy.set_mode.assert_awaited_with(105625, ZoneMode.AUTO)

    await service.async_set_target_temperature(105625, 20.0)
    legacy.set_target_temperature.assert_awaited_with(105625, 20.0)

    await service.async_boost(105625, 1, 21.0)
    legacy.boost.assert_awaited_with(105625, 1, 21.0)

    await service.async_cancel_boost(105625)
    legacy.cancel_boost.assert_awaited_with(105625)

    await service.async_set_advance(105625, True)
    legacy.set_advance.assert_awaited_with(105625, True)

    with pytest.raises(ZoneNotFound):
        service.get_zone(999)
