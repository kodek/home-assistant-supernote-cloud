"""Supernote Cloud API client helper."""

from supernote.client.api import Supernote

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client

from .auth import ConfigEntryAuth
from .const import CONF_HOST, DEFAULT_HOST


async def async_get_supernote_client(
    hass: HomeAssistant, entry: ConfigEntry
) -> Supernote:
    """Get an authenticated Supernote API client."""
    session = aiohttp_client.async_get_clientsession(hass)
    host = entry.options.get(CONF_HOST, DEFAULT_HOST)
    auth = ConfigEntryAuth(hass, entry, session)
    return Supernote.from_auth(auth, host=host, session=session)
