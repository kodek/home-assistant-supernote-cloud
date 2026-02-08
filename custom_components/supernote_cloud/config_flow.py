"""Config flow for supernote_cloud integration."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any
import logging

import voluptuous as vol
from supernote.cloud.exceptions import (
    SupernoteException,
    ApiException,
    SmsVerificationRequired,
)
from supernote.cloud.auth import ConstantAuth
from supernote.cloud.login_client import LoginClient
from supernote.cloud.client import Client
from supernote.cloud.cloud_client import SupernoteCloudClient

from homeassistant.core import callback
from homeassistant.config_entries import (
    ConfigFlow,
    ConfigFlowResult,
    SOURCE_REAUTH,
    ConfigEntry,
    OptionsFlow,
)
from homeassistant.helpers import selector
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaFlowFormStep,
    SchemaOptionsFlowHandler,
)
from homeassistant.util import dt as dt_util
from homeassistant.helpers.aiohttp_client import (
    async_get_clientsession,
)
from homeassistant.const import (
    CONF_ACCESS_TOKEN,
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_UNIQUE_ID,
)

from .const import DOMAIN, CONF_API_USERNAME, CONF_TOKEN_TIMESTAMP

_LOGGER = logging.getLogger(__name__)

OPTIONS_FLOW = {
    "init": SchemaFlowFormStep(),
}


class SupernoteCloudConfigFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Supernote Cloud."""

    VERSION = 1
    MINOR_VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._username: str | None = None
        self._password: str | None = None
        self._sms_timestamp: str | None = None

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> OptionsFlow:
        """Create the options flow."""
        return SchemaOptionsFlowHandler(config_entry, OPTIONS_FLOW)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._username = user_input[CONF_USERNAME]
            self._password = user_input[CONF_PASSWORD]

            websession = async_get_clientsession(self.hass)
            login_client = LoginClient(Client(websession))

            try:
                access_token = await login_client.login(self._username, self._password)
                return await self._async_create_supernote_entry(access_token)
            except SmsVerificationRequired as err:
                self._sms_timestamp = err.timestamp
                # Request SMS code
                try:
                    await login_client.request_sms_code(self._username)
                except (ApiException, SupernoteException):
                    errors["base"] = "api_error"
                else:
                    return await self.async_step_sms()
            except (ApiException, SupernoteException):
                errors["base"] = "api_error"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERNAME): selector.TextSelector(
                        selector.TextSelectorConfig(),
                    ),
                    vol.Required(CONF_PASSWORD): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.PASSWORD
                        ),
                    ),
                }
            ),
            errors=errors or None,
        )

    async def async_step_sms(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the SMS verification step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            code = user_input["code"]
            websession = async_get_clientsession(self.hass)
            login_client = LoginClient(Client(websession))

            try:
                access_token = await login_client.sms_login(
                    self._username,
                    code,
                    self._sms_timestamp,  # type: ignore[arg-type]
                )
                return await self._async_create_supernote_entry(access_token)
            except (ApiException, SupernoteException):
                errors["base"] = "invalid_auth"

        return self.async_show_form(
            step_id="sms",
            data_schema=vol.Schema(
                {
                    vol.Required("code"): selector.TextSelector(
                        selector.TextSelectorConfig(),
                    ),
                }
            ),
            errors=errors or None,
        )

    async def _async_create_supernote_entry(
        self, access_token: str
    ) -> ConfigFlowResult:
        """Create the config entry."""
        # Verify the API works and get user info
        websession = async_get_clientsession(self.hass)
        supernote_client = SupernoteCloudClient(
            Client(websession, auth=ConstantAuth(access_token))
        )
        user_response = await supernote_client.query_user(self._username)  # type: ignore[arg-type]

        await self.async_set_unique_id(str(user_response.user_id))

        if self.source == SOURCE_REAUTH:
            self._abort_if_unique_id_mismatch()
            reauth_entry = self.hass.config_entries.async_get_entry(
                self.context["entry_id"]
            )
            return self.async_update_reload_and_abort(
                reauth_entry,  # type: ignore[arg-type]
                title=user_response.user_name,
                data={},
                options={
                    CONF_USERNAME: self._username,
                    CONF_PASSWORD: self._password,
                    CONF_ACCESS_TOKEN: access_token,
                    CONF_UNIQUE_ID: str(user_response.user_id),
                    CONF_API_USERNAME: user_response.user_name,
                    CONF_TOKEN_TIMESTAMP: dt_util.now().timestamp(),
                },
            )

        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=user_response.user_name,
            data={},
            options={
                CONF_USERNAME: self._username,
                CONF_PASSWORD: self._password,
                CONF_ACCESS_TOKEN: access_token,
                CONF_UNIQUE_ID: str(user_response.user_id),
                CONF_API_USERNAME: user_response.user_name,
                CONF_TOKEN_TIMESTAMP: dt_util.now().timestamp(),
            },
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform reauth upon an API authentication error."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Dialog that informs the user that reauth is required."""
        if user_input is None:
            return self.async_show_form(
                step_id="reauth_confirm",
                data_schema=vol.Schema({}),
            )
        return await self.async_step_user()
