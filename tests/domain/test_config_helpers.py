"""Tests for config helper mapping (no Home Assistant import)."""

from __future__ import annotations

from custom_components.eph_ember.const import (
    API_VERSION_AUTO,
    API_VERSION_CURRENT,
    API_VERSION_LEGACY,
)
from custom_components.eph_ember.domain.models import ApiKind


def api_kind_from_config(value: str | None) -> ApiKind:
    """Mirror into.ha.dependencies.api_kind_from_config without HA imports."""
    mapping = {
        API_VERSION_AUTO: ApiKind.AUTO,
        API_VERSION_LEGACY: ApiKind.LEGACY,
        API_VERSION_CURRENT: ApiKind.CURRENT,
    }
    return mapping.get(value or API_VERSION_AUTO, ApiKind.AUTO)


# Keep in sync with into.ha.dependencies.TO_REDACT. The integration redacts via
# homeassistant.components.diagnostics.async_redact_data, which also walks
# nested dicts and lists. This mirror stays importable without Home Assistant.
_REDACT_KEYS = {
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
    redacted = dict(data)
    for key in _REDACT_KEYS:
        if key in redacted and redacted[key] not in (None, ""):
            redacted[key] = "**REDACTED**"
    return redacted


def test_api_kind_mapping() -> None:
    assert api_kind_from_config("auto") == ApiKind.AUTO
    assert api_kind_from_config("legacy") == ApiKind.LEGACY
    assert api_kind_from_config("current") == ApiKind.CURRENT
    assert api_kind_from_config(None) == ApiKind.AUTO


def test_redact_config() -> None:
    assert redact_config(
        {
            "username": "a@b.c",
            "password": "secret",
            "token": "t",
            "refresh_token": "r",
            "title": "a@b.c",
            "gateway_id": "GW01-1",
            "name": "Home",
            "home_id": 40421,
            "weather_location": "Belfast",
            "invite_code": "52644",
            "api_version": "auto",
        }
    ) == {
        "username": "**REDACTED**",
        "password": "**REDACTED**",
        "token": "**REDACTED**",
        "refresh_token": "**REDACTED**",
        "title": "**REDACTED**",
        "gateway_id": "**REDACTED**",
        "name": "**REDACTED**",
        "home_id": "**REDACTED**",
        "weather_location": "**REDACTED**",
        "invite_code": "**REDACTED**",
        "api_version": "auto",
    }
