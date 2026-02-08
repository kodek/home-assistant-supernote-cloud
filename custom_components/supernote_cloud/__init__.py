"""supernote_cloud custom component."""

from __future__ import annotations

import logging

from supernote.client.api import Supernote

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, CONF_HOST, DEFAULT_HOST
from .auth import ConfigEntryAuth
from .types import SupernoteCloudConfigEntry
from .media_source import async_register_http_views

from .llm import async_register_llm_apis

__all__ = ["DOMAIN"]

_LOGGER = logging.getLogger(__name__)

PLATFORMS: tuple[Platform] = ()  # type: ignore[assignment]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the supernote_cloud component."""
    async_register_http_views(hass)
    return True


async def async_setup_entry(
    hass: HomeAssistant, entry: SupernoteCloudConfigEntry
) -> bool:
    """Set up a config entry."""

    session = aiohttp_client.async_get_clientsession(hass)
    host = entry.options.get(CONF_HOST, DEFAULT_HOST)
    auth = ConfigEntryAuth(hass, entry, session)
    sn = Supernote.from_auth(auth, host=host, session=session)

    entry.runtime_data = sn

    await hass.config_entries.async_forward_entry_setups(
        entry,
        platforms=PLATFORMS,
    )
    await async_register_llm_apis(hass, entry)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(
        entry,
        PLATFORMS,
    )
