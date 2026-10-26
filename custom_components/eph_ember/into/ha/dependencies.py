"""Composition helpers for wiring Home Assistant to the domain."""

from __future__ import annotations

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from ...const import (
    API_VERSION_AUTO,
    API_VERSION_CURRENT,
    API_VERSION_LEGACY,
    CONF_API_VERSION,
    DEFAULT_API_VERSION,
)
from ...domain.heating_service import HeatingService
from ...domain.models import ApiKind
from ...out.current.gateway import CurrentGateway
from ...out.legacy.gateway import LegacyGateway


def api_kind_from_config(value: str | None) -> ApiKind:
    """Map stored config to ApiKind."""
    mapping = {
        API_VERSION_AUTO: ApiKind.AUTO,
        API_VERSION_LEGACY: ApiKind.LEGACY,
        API_VERSION_CURRENT: ApiKind.CURRENT,
    }
    return mapping.get(value or DEFAULT_API_VERSION, ApiKind.AUTO)


def build_heating_service(hass: HomeAssistant, entry: ConfigEntry) -> HeatingService:
    """Construct a HeatingService from a config entry."""
    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]
    api_version = api_kind_from_config(
        entry.options.get(CONF_API_VERSION, entry.data.get(CONF_API_VERSION))
    )
    session = async_get_clientsession(hass)
    legacy = LegacyGateway(session, username, password)
    current = CurrentGateway(username, password)
    return HeatingService(legacy=legacy, current=current, api_version=api_version)


# Keys scrubbed from shared diagnostics. username/title are the account email,
# gateway_id is the gateway serial, and weather_location is a place name.
TO_REDACT = {
    "password",
    "token",
    "refresh_token",
    "username",
    "title",
    "gateway_id",
    "name",
    "home_id",
    "weather_location",
    "invite_code",
}


def redact_config(data: dict) -> dict:
    """Return a copy of config data with secrets and identifiers removed."""
    return async_redact_data(data, TO_REDACT)
