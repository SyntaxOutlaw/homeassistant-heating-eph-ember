"""Register the EPH Ember Lovelace climate card."""

from __future__ import annotations

import logging
from pathlib import Path

from homeassistant.components.http import StaticPathConfig
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.event import async_call_later

from ...const import DOMAIN

_LOGGER = logging.getLogger(__name__)

_FRONTEND_KEY = f"{DOMAIN}_frontend_registered"
_URL_BASE = f"/{DOMAIN}-local"
_CARD_PATH = "ephember-climate-card.js"
# Bump when the card JS changes so browsers fetch a fresh copy.
_CARD_VERSION = "1.2.0"


async def async_register_frontend(hass: HomeAssistant) -> None:
    """Serve www/ and ensure the Lovelace module resource exists."""
    if hass.data.get(_FRONTEND_KEY):
        return
    hass.data[_FRONTEND_KEY] = True

    www = Path(__file__).resolve().parents[2] / "www"
    if not www.is_dir():
        _LOGGER.warning("EPH frontend www/ folder missing at %s", www)
        return

    try:
        await hass.http.async_register_static_paths(
            [StaticPathConfig(_URL_BASE, str(www), False)]
        )
    except RuntimeError:
        # Already registered on reload.
        pass

    async def _ensure_resource(_arg: object | None = None) -> None:
        await _async_ensure_lovelace_resource(hass)

    if hass.is_running:
        # Defer slightly so lovelace resources storage is ready after reload.
        async_call_later(hass, 1.0, _ensure_resource)
    else:

        @callback
        def _on_started(event: Event) -> None:
            hass.async_create_task(_ensure_resource(event))

        hass.bus.async_listen_once("homeassistant_started", _on_started)


async def _async_ensure_lovelace_resource(hass: HomeAssistant) -> None:
    """Add/update the card module in Lovelace resources (storage mode)."""
    url = f"{_URL_BASE}/{_CARD_PATH}?v={_CARD_VERSION}"
    try:
        lovelace = hass.data.get("lovelace")
        if lovelace is None:
            _LOGGER.debug(
                "Lovelace not ready; add resource manually: %s", url
            )
            return

        # YAML mode: resources live in configuration — do not write storage.
        mode = getattr(lovelace, "mode", None)
        if mode == "yaml":
            _LOGGER.info(
                "Lovelace is in YAML mode — add this resource manually: %s", url
            )
            return

        resources = getattr(lovelace, "resources", None)
        if resources is None:
            return

        if hasattr(resources, "async_load") and not getattr(resources, "loaded", True):
            await resources.async_load()

        existing = None
        for item in resources.async_items():
            item_url = item.get("url", "")
            if _CARD_PATH in item_url or item_url.startswith(f"{_URL_BASE}/"):
                existing = item
                break

        if existing:
            if existing.get("url") != url:
                await resources.async_update_item(
                    existing["id"], {"res_type": "module", "url": url}
                )
                _LOGGER.debug("Updated EPH Lovelace card resource to %s", url)
            return

        await resources.async_create_item({"res_type": "module", "url": url})
        _LOGGER.info("Registered EPH Lovelace card resource %s", url)
    except Exception:  # noqa: BLE001 — never block integration setup on UI extras
        _LOGGER.exception(
            "Could not auto-register Lovelace card; add manually: %s", url
        )
