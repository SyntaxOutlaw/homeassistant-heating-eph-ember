"""Outbound port for EMBER cloud gateways."""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..domain.models import Home, Zone, ZoneMode


class EmberGateway(ABC):
    """
    Port for EMBER cloud I/O.

    Implementations perform HTTP or library calls and map responses into
    domain models only. Detection and command orchestration live in the
    domain layer.
    """

    @abstractmethod
    async def login(self) -> None:
        """Authenticate with username/password and store tokens in memory."""

    @abstractmethod
    async def list_homes(self) -> list[Home]:
        """Return homes/gateways for the authenticated account."""

    @abstractmethod
    async def list_zones(self, gateway_id: str) -> list[Zone]:
        """Return current zone state for a gateway."""

    @abstractmethod
    async def set_mode(self, zone_id: int, mode: ZoneMode) -> None:
        """Set the run selection / mode for a zone."""

    @abstractmethod
    async def set_target_temperature(self, zone_id: int, temperature: float) -> None:
        """Set the target temperature for a zone."""

    @abstractmethod
    async def boost(self, zone_id: int, hours: int, temperature: float) -> None:
        """Activate boost for a zone."""

    @abstractmethod
    async def cancel_boost(self, zone_id: int) -> None:
        """Cancel an active boost."""

    @abstractmethod
    async def set_advance(self, zone_id: int, active: bool) -> None:
        """Enable or cancel schedule advance for a zone."""
