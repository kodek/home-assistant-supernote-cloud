"""Config flow for supernote_cloud integration."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast
import logging

import voluptuous as vol

from homeassistant.config_entries import ConfigFlowResult
from homeassistant.helpers import selector
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaCommonFlowHandler,
    SchemaConfigFlowHandler,
    SchemaFlowFormStep,
    SchemaFlowError,
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
from .supernote_client.auth import (
    LoginClient,
    Client,
    SupernoteCloudClient,
    ConstantAuth,
)
from .supernote_client.exceptions import SupernoteException, ApiException

_LOGGER = logging.getLogger(__name__)


async def validate_user_input(
    handler: SchemaCommonFlowHandler, user_input: dict[str, Any]
) -> dict[str, Any]:
    """Validate user input."""
    handler.parent_handler._async_abort_entries_match(  # noqa: SLF001
        {CONF_USERNAME: user_input[CONF_USERNAME]}
    )
    websession = async_get_clientsession(handler.parent_handler.hass)
    login_client = LoginClient(Client(websession))
    try:
        access_token = await login_client.login(
            user_input[CONF_USERNAME], user_input[CONF_PASSWORD]
        )
    except (ApiException, SupernoteException) as err:
        _LOGGER.debug("Login api exception: %s", err)
        raise SchemaFlowError("api_error") from err

    # Verify the API works
    supernote_client = SupernoteCloudClient(
        Client(websession, auth=ConstantAuth(access_token))
    )
    try:
        user_response = await supernote_client.query_user(user_input[CONF_USERNAME])
    except (ApiException, SupernoteException) as err:
        _LOGGER.debug("Query api exception: %s", err)
        raise SchemaFlowError("api_error") from err
    await handler.parent_handler.async_set_unique_id(unique_id=str(user_response.user_id))  # type: ignore[union-attr]
    handler.parent_handler._abort_if_unique_id_configured()  # type: ignore[union-attr]
    return {
        **user_input,
        CONF_ACCESS_TOKEN: access_token,
        CONF_UNIQUE_ID: str(user_response.user_id),
        CONF_API_USERNAME: user_response.user_name,
        CONF_PASSWORD: user_input[CONF_PASSWORD],
        CONF_TOKEN_TIMESTAMP: dt_util.now().timestamp(),
    }


CONFIG_FLOW = {
    "user": SchemaFlowFormStep(
        schema=vol.Schema(
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
        validate_user_input=validate_user_input,
    )
}

OPTIONS_FLOW = {
    "init": SchemaFlowFormStep(),
}


class SupernoteCloudConfigFlowHandler(SchemaConfigFlowHandler, domain=DOMAIN):
    """Handle a config flow for Switch as X."""

    config_flow = CONFIG_FLOW
    options_flow = OPTIONS_FLOW

    VERSION = 1
    MINOR_VERSION = 1

    def async_config_entry_title(self, options: Mapping[str, Any]) -> str:
        """Return config entry title."""
        return cast(str, options[CONF_API_USERNAME])

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

    # async def async_oauth_create_entry(self, data: dict) -> ConfigFlowResult:
    #     """Create an oauth config entry or update existing entry for reauth."""
    #     data[CONF_TOKEN_TIMESTAMP] = dt_util.now().timestamp()
    #     if self.source == SOURCE_REAUTH:
    #         self._abort_if_unique_id_mismatch()
    #         return self.async_update_reload_and_abort(
    #             self._get_reauth_entry(),
    #             data_updates=data,
    #         )
    #     self._abort_if_unique_id_configured()
    #     return await super().async_oauth_create_entry(data)  # type: ignore[no-any-return]
