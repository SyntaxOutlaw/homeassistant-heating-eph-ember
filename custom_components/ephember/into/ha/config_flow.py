"""Config flow for EPH Controls."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from ...const import (
    API_VERSION_AUTO,
    API_VERSION_CURRENT,
    API_VERSION_LEGACY,
    CONF_API_VERSION,
    DEFAULT_API_VERSION,
    DOMAIN,
)
from ...domain.heating_service import HeatingService
from ...domain.models import ApiKind
from ...error_handling import EmberApiError, InvalidCredentials
from ...out.current.gateway import CurrentGateway
from ...out.legacy.gateway import LegacyGateway
from .dependencies import api_kind_from_config

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Optional(CONF_API_VERSION, default=DEFAULT_API_VERSION): vol.In(
            [API_VERSION_AUTO, API_VERSION_LEGACY, API_VERSION_CURRENT]
        ),
    }
)

STEP_REAUTH_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PASSWORD): str,
    }
)

STEP_RECONFIGURE_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_VERSION, default=DEFAULT_API_VERSION): vol.In(
            [API_VERSION_AUTO, API_VERSION_LEGACY, API_VERSION_CURRENT]
        ),
    }
)


class EphEmberConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle an EPH Controls config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize flow state."""
        self._reauth_entry: ConfigEntry | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial user step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            username = user_input[CONF_USERNAME].strip()
            password = user_input[CONF_PASSWORD]
            api_version = user_input.get(CONF_API_VERSION, DEFAULT_API_VERSION)
            try:
                await self._async_validate(username, password, api_version)
            except InvalidCredentials:
                errors["base"] = "invalid_auth"
            except EmberApiError:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(username.lower())
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=username,
                    data={
                        CONF_USERNAME: username,
                        CONF_PASSWORD: password,
                        CONF_API_VERSION: api_version,
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Import from YAML climate platform configuration."""
        username = str(import_data[CONF_USERNAME]).strip()
        password = str(import_data[CONF_PASSWORD])
        await self.async_set_unique_id(username.lower())
        self._abort_if_unique_id_configured()
        try:
            await self._async_validate(username, password, DEFAULT_API_VERSION)
        except InvalidCredentials:
            return self.async_abort(reason="invalid_auth")
        except EmberApiError:
            return self.async_abort(reason="cannot_connect")
        return self.async_create_entry(
            title=username,
            data={
                CONF_USERNAME: username,
                CONF_PASSWORD: password,
                CONF_API_VERSION: DEFAULT_API_VERSION,
            },
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Start reauthentication."""
        self._reauth_entry = self._get_reauth_entry()
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm reauthentication with a new password."""
        errors: dict[str, str] = {}
        entry = self._reauth_entry or self._get_reauth_entry()
        if user_input is not None:
            username = entry.data[CONF_USERNAME]
            password = user_input[CONF_PASSWORD]
            api_version = entry.data.get(CONF_API_VERSION, DEFAULT_API_VERSION)
            try:
                await self._async_validate(username, password, api_version)
            except InvalidCredentials:
                errors["base"] = "invalid_auth"
            except EmberApiError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates={CONF_PASSWORD: password},
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=STEP_REAUTH_DATA_SCHEMA,
            errors=errors,
            description_placeholders={"username": entry.data[CONF_USERNAME]},
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Allow changing api_version without recreating the entry."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            api_version = user_input[CONF_API_VERSION]
            try:
                await self._async_validate(
                    entry.data[CONF_USERNAME],
                    entry.data[CONF_PASSWORD],
                    api_version,
                )
            except InvalidCredentials:
                errors["base"] = "invalid_auth"
            except EmberApiError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates={CONF_API_VERSION: api_version},
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                STEP_RECONFIGURE_DATA_SCHEMA,
                {
                    CONF_API_VERSION: entry.data.get(
                        CONF_API_VERSION, DEFAULT_API_VERSION
                    )
                },
            ),
            errors=errors,
        )

    async def _async_validate(
        self, username: str, password: str, api_version: str
    ) -> None:
        """Validate credentials by logging in and listing homes/zones."""
        session = async_get_clientsession(self.hass)
        legacy = LegacyGateway(session, username, password)
        current = CurrentGateway(username, password)
        service = HeatingService(
            legacy=legacy,
            current=current,
            api_version=api_kind_from_config(api_version),
        )
        await service.async_setup()
        await service.async_refresh_zones()

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Create the options flow."""
        return EphEmberOptionsFlow()


class EphEmberOptionsFlow(OptionsFlow):
    """Handle options for API version override."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current = self.config_entry.options.get(
            CONF_API_VERSION,
            self.config_entry.data.get(CONF_API_VERSION, DEFAULT_API_VERSION),
        )
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_API_VERSION, default=current): vol.In(
                        [API_VERSION_AUTO, API_VERSION_LEGACY, API_VERSION_CURRENT]
                    ),
                }
            ),
        )
