"""Domain models for EPH Controls heating."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum, IntEnum


class ZoneMode(IntEnum):
    """Run selection / zone mode values used by both API generations."""

    AUTO = 0
    ALL_DAY = 1
    ON = 2
    OFF = 3


class ApiKind(str, Enum):
    """Which EMBER API generation a home uses."""

    AUTO = "auto"
    LEGACY = "legacy"
    CURRENT = "current"


class HvacDemand(str, Enum):
    """Whether a zone appears to be calling for heat."""

    OFF = "off"
    HEATING = "heating"
    IDLE = "idle"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class Home:
    """A gateway / home associated with an EMBER account."""

    gateway_id: str
    name: str
    device_type: int | None
    system_type: str | None
    zone_count: int | None
    api_kind: ApiKind
    home_id: int | None = None
    invite_code: str | None = None
    is_online: bool | None = None
    weather_location: str | None = None
    holiday_mode_active: bool | None = None
    frost_protection_enabled: bool | None = None
    frost_protection_temperature: float | None = None
    quick_boost_temperature: float | None = None
    gateway_datetime: str | None = None
    utc_time_offset: str | None = None

    @property
    def supports_advance(self) -> bool:
        """Cloud Advance is only available on the current API path."""
        return self.api_kind == ApiKind.CURRENT

    @property
    def hardware_label(self) -> str | None:
        """Human-readable gateway label when known."""
        if self.device_type == 1 or self.system_type == "EMBER-PS":
            return "GW01"
        if self.system_type:
            return self.system_type
        if self.device_type is not None:
            return f"Type {self.device_type}"
        return None


@dataclass(frozen=True, slots=True)
class Zone:
    """Normalized zone state consumed by Home Assistant adapters."""

    zone_id: int
    gateway_id: str
    name: str
    mode: ZoneMode
    current_temperature: float | None
    target_temperature: float | None
    is_hot_water: bool
    is_online: bool
    is_boost_active: bool
    is_advance_active: bool
    boost_hours: int | None
    boost_finish: datetime | None
    prefix: str | None
    demand: HvacDemand
    api_kind: ApiKind
