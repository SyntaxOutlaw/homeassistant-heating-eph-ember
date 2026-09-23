"""Composition helpers for wiring Home Assistant to the domain."""

from __future__ import annotations

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


def redact_config(data: dict) -> dict:
    """Return a copy of config data with secrets removed."""
    redacted = dict(data)
    for key in ("password", "token", "refresh_token"):
        if key in redacted:
            redacted[key] = "**REDACTED**"
    return redacted
