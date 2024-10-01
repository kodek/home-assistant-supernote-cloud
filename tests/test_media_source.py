"""Test the Google Photos media source."""

import pytest

from homeassistant.components.media_source import (
    URI_SCHEME,
    BrowseError,
    async_browse_media,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from custom_components.supernote_cloud.const import DOMAIN

from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from .conftest import CONFIG_ENTRY_ID, CONFIG_ENTRY_TITLE

SOURCE_TITLE = "Supernote Cloud"


@pytest.fixture(autouse=True)
async def setup_components(hass: HomeAssistant) -> None:
    """Fixture to initialize the integration."""
    await async_setup_component(hass, "media_source", {})


@pytest.mark.usefixtures("setup_integration")
async def test_no_config_entries(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test a media source with no active config entry."""

    await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    browse = await async_browse_media(hass, f"{URI_SCHEME}{DOMAIN}")

    assert browse.domain == DOMAIN
    assert browse.identifier is None
    assert browse.title == SOURCE_TITLE
    assert browse.can_expand
    assert not browse.children


@pytest.mark.usefixtures("setup_integration")
async def test_invalid_config_entry(hass: HomeAssistant) -> None:
    """Test browsing to a config entry that does not exist."""
    with pytest.raises(BrowseError, match="Could not find config entry"):
        await async_browse_media(hass, f"{URI_SCHEME}{DOMAIN}/invalid-config-entry")


@pytest.mark.usefixtures("setup_integration")
async def test_browse_invalid_path(hass: HomeAssistant) -> None:
    """Test browsing to an invalid node is not possible."""
    browse = await async_browse_media(hass, f"{URI_SCHEME}{DOMAIN}")
    assert browse.domain == DOMAIN
    assert browse.identifier is None
    assert browse.title == SOURCE_TITLE
    assert [(child.identifier, child.title) for child in browse.children] == [
        (CONFIG_ENTRY_ID, CONFIG_ENTRY_TITLE)
    ]

    with pytest.raises(BrowseError, match="Invalid SupernoteIdentifierType"):
        await async_browse_media(
            hass, f"{URI_SCHEME}{DOMAIN}/{CONFIG_ENTRY_ID}/q/some-id"
        )


@pytest.mark.usefixtures("setup_integration")
async def test_browse_albums(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test a media source with no eligible camera devices."""
    browse = await async_browse_media(hass, f"{URI_SCHEME}{DOMAIN}")
    assert browse.domain == DOMAIN
    assert browse.identifier is None
    assert browse.title == SOURCE_TITLE
    assert [(child.identifier, child.title) for child in browse.children] == [
        (CONFIG_ENTRY_ID, CONFIG_ENTRY_TITLE)
    ]

    aioclient_mock.post(
        "https://cloud.supernote.com/api/file/list/query",
        json={
            "success": True,
            "total": 3,
            "size": 10,
            "pages": 1,
            "userFileVOList": [
                {
                    "id": "1111111111111111",
                    "directoryId": "222222222",
                    "fileName": "Folder title",
                    "isFolder": "Y",
                    "createTime": 1727759196000,
                    "updateTime": 1727759196000
                },
            ]
        },
    )

    browse = await async_browse_media(hass, f"{URI_SCHEME}{DOMAIN}/{CONFIG_ENTRY_ID}")
    assert browse.domain == DOMAIN
    assert browse.identifier == CONFIG_ENTRY_ID
    assert browse.title == CONFIG_ENTRY_TITLE
    folder_path = f"{CONFIG_ENTRY_ID}/f/1111111111111111"
    assert [(child.identifier, child.title) for child in browse.children] == [
        (folder_path, "Folder title"),
    ]

    aioclient_mock.clear_requests()
    aioclient_mock.post(
        "https://cloud.supernote.com/api/file/list/query",
        json={
            "success": True,
            "total": 10,
            "size": 20,
            "pages": 1,
            "userFileVOList": [
                {
                    "id": "33333333333",
                    "directoryId": "222222222",
                    "fileName": "Note title",
                    "isFolder": "N",
                    "size": 12345,
                    "md5": "abcdefabcdefabcdefabcdefabcdef",
                    "createTime": 1727759196000,
                    "updateTime": 1727759196000
                },
            ]
        },
    )

    browse = await async_browse_media(hass, f"{URI_SCHEME}{DOMAIN}/{folder_path}")
    assert browse.domain == DOMAIN
    assert browse.identifier == folder_path
    assert browse.title == CONFIG_ENTRY_TITLE
    assert [(child.identifier, child.title) for child in browse.children] == [
        (f"{CONFIG_ENTRY_ID}/f/33333333333", "Note title")
    ]
