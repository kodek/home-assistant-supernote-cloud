"""Test the Google Photos media source."""

import pytest
from unittest.mock import patch
from http import HTTPStatus

from homeassistant.components.media_source import (
    URI_SCHEME,
    BrowseError,
    async_browse_media,
    async_resolve_media,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from custom_components.supernote_cloud.const import DOMAIN

from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.typing import ClientSessionGenerator
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from .conftest import CONFIG_ENTRY_ID, CONFIG_ENTRY_TITLE

SOURCE_TITLE = "Supernote Cloud"
ROOT_FOLDER_PATH = f"{CONFIG_ENTRY_ID}/f/0"
CONTENT_BYTES = "some-content".encode("utf-8")


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
async def test_invalid_path(hass: HomeAssistant) -> None:
    """Test browsing to a path with an incorrect format."""
    with pytest.raises(BrowseError, match="Invalid identifier"):
        await async_browse_media(hass, f"{URI_SCHEME}{DOMAIN}/invalid-config-entry")


@pytest.mark.usefixtures("setup_integration")
async def test_browse_invalid_path(hass: HomeAssistant) -> None:
    """Test browsing to an invalid node is not possible."""
    browse = await async_browse_media(hass, f"{URI_SCHEME}{DOMAIN}")
    assert browse.domain == DOMAIN
    assert browse.identifier is None
    assert browse.title == SOURCE_TITLE
    assert [(child.identifier, child.title) for child in browse.children] == [
        (ROOT_FOLDER_PATH, CONFIG_ENTRY_TITLE)
    ]

    with pytest.raises(BrowseError, match="Invalid identifier"):
        await async_browse_media(hass, f"{URI_SCHEME}{DOMAIN}/{CONFIG_ENTRY_ID}/f")

    with pytest.raises(BrowseError, match="Invalid identifier"):
        await async_browse_media(
            hass, f"{URI_SCHEME}{DOMAIN}/{CONFIG_ENTRY_ID}/q/some-id"
        )


@pytest.mark.usefixtures("setup_integration")
async def test_browse_folders(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test browsing the top level folder list."""
    browse = await async_browse_media(hass, f"{URI_SCHEME}{DOMAIN}")
    assert browse.domain == DOMAIN
    assert browse.identifier is None
    assert browse.title == SOURCE_TITLE
    assert [(child.identifier, child.title) for child in browse.children] == [
        (ROOT_FOLDER_PATH, CONFIG_ENTRY_TITLE)
    ]

    # Browse folders
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
                    "updateTime": 1727759196000,
                },
            ],
        },
    )

    browse = await async_browse_media(hass, f"{URI_SCHEME}{DOMAIN}/{ROOT_FOLDER_PATH}")
    assert browse.domain == DOMAIN
    assert browse.identifier == ROOT_FOLDER_PATH
    assert browse.title == CONFIG_ENTRY_TITLE
    folder_path = f"{ROOT_FOLDER_PATH}/1111111111111111"
    assert [(child.identifier, child.title) for child in browse.children] == [
        (folder_path, "Folder title"),
    ]

    # Browse contents of a subfolder
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
                    "fileName": "Note title.note",
                    "isFolder": "N",
                    "size": 12345,
                    "md5": "abcdefabcdefabcdefabcdefabcdef",
                    "createTime": 1727759196000,
                    "updateTime": 1727759196000,
                },
            ],
        },
    )
    browse = await async_browse_media(hass, f"{URI_SCHEME}{DOMAIN}/{folder_path}")
    assert browse.domain == DOMAIN
    assert browse.identifier == folder_path
    assert browse.title == "Folder title"
    note_path = f"{CONFIG_ENTRY_ID}/n/1111111111111111/33333333333"
    assert [(child.identifier, child.title) for child in browse.children] == [
        (note_path, "Note title.note")
    ]

    aioclient_mock.clear_requests()
    aioclient_mock.post(
        "https://cloud.supernote.com/api/file/download/url",
        json={"success": True, "url": "https://example.com/file-download-url"},
    )
    aioclient_mock.get(
        "https://example.com/file-download-url",
        text="file-contents",
    )

    # Browse into a note
    with patch(
        "custom_components.supernote_cloud.store.store.LocalStore.get_note_pages",
        return_value=2,
    ):
        browse = await async_browse_media(hass, f"{URI_SCHEME}{DOMAIN}/{note_path}")
        assert browse.domain == DOMAIN
        assert browse.identifier == note_path
        assert browse.title == "Note title.note"
        page_path_prefix = f"{CONFIG_ENTRY_ID}/p/1111111111111111/33333333333"
        assert [(child.identifier, child.title) for child in browse.children] == [
            (f"{page_path_prefix}/1", "Page 1"),
            (f"{page_path_prefix}/2", "Page 2"),
        ]

    media = await async_resolve_media(
        hass, f"{URI_SCHEME}{DOMAIN}/{page_path_prefix}/1", None
    )

    client = await hass_client()
    with patch(
        "custom_components.supernote_cloud.store.store.LocalStore.get_note_png",
        return_value=CONTENT_BYTES,
    ):
        response = await client.get(media.url)
        assert response.status == HTTPStatus.OK, f"Response not matched: {response}"
        contents = await response.read()
        assert contents == CONTENT_BYTES
