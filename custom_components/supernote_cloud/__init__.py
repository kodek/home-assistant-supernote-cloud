"""supernote_cloud custom component."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .api import async_get_supernote_client
from .types import SupernoteCloudConfigEntry
from .media_source import async_register_http_views

from .llm import async_register_llm_apis

__all__ = ["DOMAIN"]

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = []


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the supernote_cloud component."""
    async_register_http_views(hass)
    return True


async def async_setup_entry(
    hass: HomeAssistant, entry: SupernoteCloudConfigEntry
) -> bool:
    """Set up a config entry."""
    sn = await async_get_supernote_client(hass, entry)
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
