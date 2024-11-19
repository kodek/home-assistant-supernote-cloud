"""Supernote Cloud Auth."""

import datetime
import logging
from typing import cast

import aiohttp

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_PASSWORD, CONF_USERNAME
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util import dt as dt_util

from .const import CONF_TOKEN_TIMESTAMP, TOKEN_LIFEIME
from .supernote_client.auth import AbstractAuth, LoginClient, Client
from .supernote_client.exceptions import SupernoteException

_LOGGER = logging.getLogger(__name__)


class ConfigEntryAuth(AbstractAuth):
    """Config entry auth."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        session: aiohttp.ClientSession,
    ) -> None:
        """Initialize the auth."""
        self._hass = hass
        self._entry = entry
        self._login_client = LoginClient(Client(session))
        self._session = session

    async def async_get_access_token(self) -> str:
        """Return a valid access token."""
        if self.is_expired():
            await self._refresh_access_token()
        return cast(str, self._entry.options[CONF_ACCESS_TOKEN])

    def is_expired(self) -> bool:
        token_timestamp = self._entry.options.get(CONF_TOKEN_TIMESTAMP, 0)
        token_ts = datetime.datetime.fromtimestamp(
            int(token_timestamp), tz=datetime.timezone.utc
        )
        now = dt_util.now()
        age = now - token_ts
        return age > TOKEN_LIFEIME

    async def _refresh_access_token(self) -> None:
        """Refresh access token."""
        try:
            new_token = await self._login_client.login(
                self._entry.options[CONF_USERNAME], self._entry.options[CONF_PASSWORD]
            )
        except SupernoteException as err:
            _LOGGER.debug("Login api exception: %s", err)
            raise HomeAssistantError("API Error: {err}") from err

        self._hass.config_entries.async_update_entry(
            self._entry,
            options={
                **self._entry.options,
                CONF_ACCESS_TOKEN: new_token,
                CONF_TOKEN_TIMESTAMP: dt_util.now().timestamp(),
            },
        )
