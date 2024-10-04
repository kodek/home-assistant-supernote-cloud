"""supernote_cloud custom component."""

from __future__ import annotations

import logging
import pathlib

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform, CONF_ACCESS_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client

from .const import DOMAIN
from .types import SupernoteCloudConfigEntry
from .supernote_client.auth import SupernoteCloudClient, ConstantAuth, Client
from .store.store import LocalStore

__all__ = ["DOMAIN"]

_LOGGER = logging.getLogger(__name__)

PLATFORMS: tuple[Platform] = ()  # type: ignore[assignment]

STORE_PATH = f".storage/{DOMAIN}"


async def async_setup_entry(
    hass: HomeAssistant, entry: SupernoteCloudConfigEntry
) -> bool:
    """Set up a config entry."""

    store_path = pathlib.Path(hass.config.path(STORE_PATH))
    session = aiohttp_client.async_get_clientsession(hass)
    access_token = entry.options[CONF_ACCESS_TOKEN]
    client = Client(session, auth=ConstantAuth(access_token))
    supernote_client = SupernoteCloudClient(client)
    store = LocalStore(store_path, supernote_client)

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
