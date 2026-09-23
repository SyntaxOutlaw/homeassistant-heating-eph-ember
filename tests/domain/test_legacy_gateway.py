"""Unit tests for legacy HTTP write payloads."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.eph_ember.domain.models import ZoneMode
from custom_components.eph_ember.out.legacy.gateway import LegacyGateway


class _Resp:
    def __init__(self, payload: dict, status: int = 200) -> None:
        self.status = status
        self._payload = payload

    async def __aenter__(self) -> _Resp:
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    async def json(self, content_type: str | None = None) -> dict:
        return self._payload

    async def text(self) -> str:
        return json.dumps(self._payload)


@pytest.mark.asyncio
async def test_legacy_write_payloads_match_pyephember_031() -> None:
    session = MagicMock()
    calls: list[tuple[str, str, dict | None, dict]] = []

    def request(method: str, url: str, *, json=None, headers=None, timeout=None):
        calls.append((method, url, json, headers))
        if url.endswith("appLogin/login"):
            return _Resp({"status": 0, "data": {"token": "tok", "refresh_token": "ref"}})
        return _Resp({"status": 0, "data": None, "message": "succ."})

    session.request = MagicMock(side_effect=request)
    gateway = LegacyGateway(session, "user@example.com", "secret")
    await gateway.login()
    await gateway.set_target_temperature(105625, 18.5)
    await gateway.set_mode(105625, ZoneMode.AUTO)
    await gateway.boost(105625, 1, 20.0)
    await gateway.cancel_boost(105625)

    bodies = {url.rsplit("/", 1)[-1]: body for _, url, body, _ in calls if body is not None}
    assert bodies["setTargetTemperature"] == {"zoneid": 105625, "temperature": 18.5}
    assert bodies["setModel"] == {"zoneid": 105625, "model": 0}
    assert bodies["boost"] == {"zoneid": 105625, "hours": 1, "temperature": 20.0}
    assert bodies["cancelBoost"] == {"zoneid": 105625}

    auth_headers = [headers["Authorization"] for _, _, _, headers in calls if "Authorization" in headers]
    assert all(h == "tok" for h in auth_headers)
    assert all(not str(h).startswith("Bearer ") for h in auth_headers)


@pytest.mark.asyncio
async def test_legacy_refresh_uses_refresh_token_header() -> None:
    session = MagicMock()
    calls: list[tuple[str, str, dict]] = []

    def request(method: str, url: str, *, json=None, headers=None, timeout=None):
        calls.append((method, url, headers))
        if url.endswith("login"):
            return _Resp({"status": 0, "data": {"token": "tok1", "refresh_token": "ref1"}})
        if url.endswith("refreshAccessToken"):
            return _Resp({"status": 0, "data": {"token": "tok2", "refresh_token": "ref2"}})
        return _Resp({"status": 0, "data": []})

    session.request = MagicMock(side_effect=request)
    gateway = LegacyGateway(session, "user@example.com", "secret")
    await gateway.login()
    # Force refresh path
    gateway._token_acquired_at = gateway._token_acquired_at.replace(year=2000)
    await gateway.list_homes()

    refresh_call = next(c for c in calls if c[1].endswith("refreshAccessToken"))
    assert refresh_call[0] == "GET"
    assert refresh_call[2]["Authorization"] == "ref1"
