"""Legacy EMBER HTTP gateway (GW01 / EMBER-PS)."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from aiohttp import ClientError, ClientSession

from ...const import TEMP_SENTINEL
from ...domain.models import ApiKind, Home, HvacDemand, Zone, ZoneMode
from ...error_handling import EmberApiError, InvalidCredentials
from ...ports.gateway import EmberGateway

_LOGGER = logging.getLogger(__name__)

API_BASE = "https://eu-https.topband-cloud.com/ember-back/"
TOKEN_VALIDITY_SECONDS = 1800


def home_from_list_row(raw: dict[str, Any], *, api_kind: ApiKind = ApiKind.AUTO) -> Home:
    """Map a /homes/list row into a Home."""
    return Home(
        gateway_id=str(raw["gatewayid"]),
        name=str(raw.get("name") or "Home"),
        device_type=raw.get("deviceType"),
        system_type=raw.get("sysTemType"),
        zone_count=raw.get("zoneCount"),
        api_kind=api_kind,
    )


def home_from_detail(
    raw: dict[str, Any],
    *,
    api_kind: ApiKind = ApiKind.AUTO,
    fallback: Home | None = None,
) -> Home:
    """Map a /homes/detail payload (or nested homes object) into a Home."""
    data = raw
    if isinstance(raw.get("homes"), dict):
        data = raw["homes"]
    elif isinstance(raw.get("homes"), list) and raw["homes"]:
        data = raw["homes"][0]

    gateway_id = str(
        data.get("gatewayid")
        or data.get("gateWayId")
        or (fallback.gateway_id if fallback else "")
    )
    return Home(
        gateway_id=gateway_id,
        name=str(data.get("name") or (fallback.name if fallback else "Home")),
        device_type=data.get("deviceType", fallback.device_type if fallback else None),
        system_type=data.get("sysTemType", fallback.system_type if fallback else None),
        zone_count=data.get("zoneCount", fallback.zone_count if fallback else None),
        api_kind=api_kind,
        home_id=_optional_int(data.get("homeid")),
        invite_code=_optional_str(data.get("invitecode")),
        is_online=data.get("isonline") if "isonline" in data else (
            fallback.is_online if fallback else None
        ),
        weather_location=_optional_str(data.get("weatherlocation")),
        holiday_mode_active=data.get("holidaymodeactive")
        if "holidaymodeactive" in data
        else (fallback.holiday_mode_active if fallback else None),
        frost_protection_enabled=data.get("frostprotectionenabled")
        if "frostprotectionenabled" in data
        else (fallback.frost_protection_enabled if fallback else None),
        frost_protection_temperature=normalize_temperature(
            data.get("frostprotectiontemperature")
        )
        if data.get("frostprotectiontemperature") is not None
        else (fallback.frost_protection_temperature if fallback else None),
        quick_boost_temperature=normalize_temperature(data.get("quickboosttemperature"))
        if data.get("quickboosttemperature") is not None
        else (fallback.quick_boost_temperature if fallback else None),
        gateway_datetime=_optional_str(data.get("gatewaydatetime")),
        utc_time_offset=_optional_str(data.get("utctimeoffset")),
    )


def _optional_str(value: Any) -> str | None:
    if value is None or value == "":
        return None
    return str(value)


def _optional_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def normalize_temperature(value: Any) -> float | None:
    """Map API temperature sentinels to None."""
    if value is None:
        return None
    try:
        temp = float(value)
    except (TypeError, ValueError):
        return None
    if temp <= TEMP_SENTINEL + 0.1:
        return None
    return temp


def demand_from_legacy_zone(zone: dict[str, Any], mode: ZoneMode) -> HvacDemand:
    """Infer heat demand from legacy prefix / boost / advance flags."""
    if mode == ZoneMode.OFF:
        return HvacDemand.OFF
    prefix = zone.get("prefix") or ""
    if " off " in prefix:
        return HvacDemand.IDLE
    if "active " in prefix or "ON mode" in prefix:
        return HvacDemand.HEATING
    if zone.get("isboostactive") or zone.get("isadvanceactive"):
        return HvacDemand.HEATING
    return HvacDemand.IDLE


def parse_boost_finish(zone: dict[str, Any]) -> datetime | None:
    """Parse boost finish datetime when boost is active."""
    activation = zone.get("boostActivations")
    if not activation:
        return None
    finish = activation.get("finishdatetime") or activation.get("dispayFinishdatetime")
    if not finish:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(finish, fmt).replace(tzinfo=UTC)
        except ValueError:
            continue
    return None


def zone_from_polling(raw: dict[str, Any], gateway_id: str) -> Zone:
    """Map a /zones/polling row into a domain Zone."""
    mode = ZoneMode(int(raw.get("mode", ZoneMode.AUTO)))
    boost_hours = None
    activation = raw.get("boostActivations")
    if activation and activation.get("numberofhours") is not None:
        boost_hours = int(activation["numberofhours"])
    # Prefer live target; fall back to last stored setpoint when the live
    # value is the offline sentinel (-300).
    target = normalize_temperature(raw.get("targettemperature"))
    if target is None:
        target = normalize_temperature(raw.get("storedtargettemperature"))
    return Zone(
        zone_id=int(raw["zoneid"]),
        gateway_id=gateway_id,
        name=str(raw.get("name") or f"Zone {raw['zoneid']}"),
        mode=mode,
        current_temperature=normalize_temperature(raw.get("currenttemperature")),
        target_temperature=target,
        is_hot_water=bool(raw.get("ishotwater")),
        is_online=bool(raw.get("isonline")),
        is_boost_active=bool(raw.get("isboostactive")),
        is_advance_active=bool(raw.get("isadvanceactive")),
        boost_hours=boost_hours,
        boost_finish=parse_boost_finish(raw),
        prefix=raw.get("prefix"),
        demand=demand_from_legacy_zone(raw, mode),
        api_kind=ApiKind.LEGACY,
    )


class LegacyGateway(EmberGateway):
    """Async client for the legacy EMBER HTTP API used by GW01."""

    def __init__(
        self,
        session: ClientSession,
        username: str,
        password: str,
        *,
        api_base: str = API_BASE,
    ) -> None:
        self._session = session
        self._username = username
        self._password = password
        self._api_base = api_base.rstrip("/") + "/"
        self._token: str | None = None
        self._refresh_token: str | None = None
        self._token_acquired_at: datetime | None = None

    async def login(self) -> None:
        """Authenticate with username/password."""
        payload = await self._request(
            "POST",
            "appLogin/login",
            json_body={
                "userName": self._username,
                "password": self._password,
                "model": "HomeAssistant",
                "os": "Linux",
            },
            send_token=False,
        )
        data = payload.get("data") or {}
        if payload.get("status") != 0 or "token" not in data:
            raise InvalidCredentials("Unable to login to EPH Ember")
        self._token = data["token"]
        self._refresh_token = data.get("refresh_token")
        self._token_acquired_at = datetime.now(UTC)

    async def list_homes(self) -> list[Home]:
        """Return homes from /homes/list, enriched with /homes/detail."""
        await self._ensure_auth()
        payload = await self._request("GET", "homes/list")
        if payload.get("status") != 0:
            raise EmberApiError(
                payload.get("message") or "Failed to list homes",
                status=payload.get("status"),
            )
        homes: list[Home] = []
        for raw in payload.get("data") or []:
            summary = home_from_list_row(raw)
            try:
                detail_payload = await self._request(
                    "POST",
                    "homes/detail",
                    json_body={"gateWayId": summary.gateway_id},
                )
            except EmberApiError as err:
                _LOGGER.warning(
                    "Failed to fetch homes/detail for %s: %s", summary.gateway_id, err
                )
                homes.append(summary)
                continue
            if detail_payload.get("status") != 0:
                _LOGGER.warning(
                    "homes/detail for %s returned status %s",
                    summary.gateway_id,
                    detail_payload.get("status"),
                )
                homes.append(summary)
                continue
            homes.append(
                home_from_detail(
                    detail_payload.get("data") or {},
                    fallback=summary,
                )
            )
        return homes

    async def list_zones(self, gateway_id: str) -> list[Zone]:
        """Return zones from /zones/polling."""
        await self._ensure_auth()
        payload = await self._request(
            "POST",
            "zones/polling",
            json_body={"gateWayId": gateway_id},
        )
        if payload.get("status") != 0:
            raise EmberApiError(
                payload.get("message") or "Failed to poll zones",
                status=payload.get("status"),
            )
        return [
            zone_from_polling(raw, gateway_id) for raw in (payload.get("data") or [])
        ]

    async def set_mode(self, zone_id: int, mode: ZoneMode) -> None:
        """POST /zones/setModel with integer model (pyephember 0.3.1)."""
        await self._ensure_auth()
        payload = await self._request(
            "POST",
            "zones/setModel",
            json_body={"zoneid": zone_id, "model": int(mode)},
        )
        if payload.get("status") != 0:
            raise EmberApiError(
                payload.get("message") or "Failed to set mode",
                status=payload.get("status"),
            )

    async def set_target_temperature(self, zone_id: int, temperature: float) -> None:
        """POST /zones/setTargetTemperature."""
        await self._ensure_auth()
        payload = await self._request(
            "POST",
            "zones/setTargetTemperature",
            json_body={"zoneid": zone_id, "temperature": temperature},
        )
        if payload.get("status") != 0:
            raise EmberApiError(
                payload.get("message") or "Failed to set target temperature",
                status=payload.get("status"),
            )

    async def boost(self, zone_id: int, hours: int, temperature: float) -> None:
        """POST /zones/boost."""
        await self._ensure_auth()
        payload = await self._request(
            "POST",
            "zones/boost",
            json_body={
                "zoneid": zone_id,
                "hours": hours,
                "temperature": temperature,
            },
        )
        if payload.get("status") != 0:
            raise EmberApiError(
                payload.get("message") or "Failed to activate boost",
                status=payload.get("status"),
            )

    async def cancel_boost(self, zone_id: int) -> None:
        """POST /zones/cancelBoost."""
        await self._ensure_auth()
        payload = await self._request(
            "POST",
            "zones/cancelBoost",
            json_body={"zoneid": zone_id},
        )
        if payload.get("status") != 0:
            raise EmberApiError(
                payload.get("message") or "Failed to cancel boost",
                status=payload.get("status"),
            )

    async def set_advance(self, zone_id: int, active: bool) -> None:
        """Legacy GW01 cloud API has no advance write endpoint."""
        raise EmberApiError(
            "Advance is not available through the cloud for this gateway; "
            "use Advance on the timeclock instead",
            status=None,
        )

    async def _ensure_auth(self) -> None:
        if self._token is None:
            await self.login()
            return
        if self._token_needs_refresh():
            if not await self._refresh_access_token():
                await self.login()

    def _token_needs_refresh(self) -> bool:
        if self._token_acquired_at is None:
            return True
        expires = self._token_acquired_at + timedelta(seconds=TOKEN_VALIDITY_SECONDS)
        return datetime.now(UTC) + timedelta(seconds=30) >= expires

    async def _refresh_access_token(self) -> bool:
        if not self._refresh_token:
            return False
        try:
            payload = await self._request(
                "GET",
                "appLogin/refreshAccessToken",
                authorization=self._refresh_token,
                send_token=False,
            )
        except (EmberApiError, InvalidCredentials, ClientError):
            _LOGGER.debug("Token refresh failed; will re-login", exc_info=True)
            return False
        data = payload.get("data") or {}
        if payload.get("status") != 0 or "token" not in data:
            return False
        self._token = data["token"]
        self._refresh_token = data.get("refresh_token", self._refresh_token)
        self._token_acquired_at = datetime.now(UTC)
        return True

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        authorization: str | None = None,
        send_token: bool = True,
    ) -> dict[str, Any]:
        headers = {
            "Accept": "application/json",
        }
        if json_body is not None:
            headers["Content-Type"] = "application/json"
        if send_token:
            if not self._token:
                raise InvalidCredentials("Not authenticated")
            headers["Authorization"] = self._token
        elif authorization is not None:
            headers["Authorization"] = authorization

        url = f"{self._api_base}{path}"
        try:
            async with self._session.request(
                method, url, json=json_body, headers=headers, timeout=20
            ) as response:
                if response.status == 403:
                    raise InvalidCredentials("EPH Ember authentication rejected")
                if response.status >= 400:
                    text = await response.text()
                    raise EmberApiError(
                        f"HTTP {response.status} from {path}: {text[:200]}",
                        status=response.status,
                    )
                return await response.json(content_type=None)
        except ClientError as err:
            raise EmberApiError(f"Connection error calling {path}: {err}") from err
