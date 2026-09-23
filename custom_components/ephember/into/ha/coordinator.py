"""Data update coordinator for EPH Controls."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from ...const import DOMAIN, SCAN_INTERVAL
from ...domain.heating_service import HeatingService
from ...domain.models import Zone
from ...error_handling import EmberApiError, InvalidCredentials

_LOGGER = logging.getLogger(__name__)


class EphEmberDataUpdateCoordinator(DataUpdateCoordinator[dict[int, Zone]]):
    """Poll zone state through HeatingService."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        service: HeatingService,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self.service = service
        self.entry = entry

    async def _async_update_data(self) -> dict[int, Zone]:
        """Fetch zones from EMBER."""
        try:
            zones = await self.service.async_refresh_zones()
        except InvalidCredentials as err:
            raise ConfigEntryAuthFailed("EPH Ember credentials are invalid") from err
        except EmberApiError as err:
            raise UpdateFailed(str(err)) from err
        return {zone.zone_id: zone for zone in zones}
