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


def redact_config(data: dict) -> dict:
    redacted = dict(data)
    for key in ("password", "token", "refresh_token"):
        if key in redacted:
            redacted[key] = "**REDACTED**"
    return redacted


def test_api_kind_mapping() -> None:
    assert api_kind_from_config("auto") == ApiKind.AUTO
    assert api_kind_from_config("legacy") == ApiKind.LEGACY
    assert api_kind_from_config("current") == ApiKind.CURRENT
    assert api_kind_from_config(None) == ApiKind.AUTO


def test_redact_config() -> None:
    assert redact_config(
        {"username": "a@b.c", "password": "secret", "token": "t", "refresh_token": "r"}
    ) == {
        "username": "a@b.c",
        "password": "**REDACTED**",
        "token": "**REDACTED**",
        "refresh_token": "**REDACTED**",
    }
