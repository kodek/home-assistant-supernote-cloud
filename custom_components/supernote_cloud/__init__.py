"""supernote_cloud custom component."""

from __future__ import annotations

import logging
import pathlib

from supernote.cloud.client import Client
from supernote.cloud.cloud_client import SupernoteCloudClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .auth import ConfigEntryAuth
from .types import SupernoteCloudConfigEntry
from .store.store import LocalStore, MetadataStore
from .media_source import async_register_http_views

__all__ = ["DOMAIN"]

_LOGGER = logging.getLogger(__name__)

PLATFORMS: tuple[Platform] = ()  # type: ignore[assignment]

STORE_PATH = f".storage/{DOMAIN}"


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the supernote_cloud component."""
    async_register_http_views(hass)
    return True


async def async_setup_entry(
    hass: HomeAssistant, entry: SupernoteCloudConfigEntry
) -> bool:
    """Set up a config entry."""

    store_path = pathlib.Path(hass.config.path(STORE_PATH)) / str(entry.entry_id)
    session = aiohttp_client.async_get_clientsession(hass)
    client = Client(session, auth=ConfigEntryAuth(hass, entry, session))
    supernote_client = SupernoteCloudClient(client)

    def reauth_cb() -> None:
        _LOGGER.debug("Reauthenticating")
        entry.async_start_reauth(hass)

    store = LocalStore(
        MetadataStore(hass, store_path), store_path, supernote_client, reauth_cb
    )

    # run in executor thread
    def mkdir() -> None:
        store_path.mkdir(parents=True, exist_ok=True)

    await hass.async_add_executor_job(mkdir)

    entry.runtime_data = store

    await hass.config_entries.async_forward_entry_setups(
        entry,
        platforms=PLATFORMS,
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(
        entry,
        PLATFORMS,
    )
