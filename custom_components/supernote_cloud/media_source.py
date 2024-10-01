"""Media source for viewing local copies of Supernote media."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import logging
from typing import Self, cast


from homeassistant.components.media_player import MediaClass, MediaType
from homeassistant.components.media_source import (
    BrowseError,
    BrowseMediaSource,
    MediaSource,
    MediaSourceItem,
)
from homeassistant.core import HomeAssistant

from . import SupernoteCloudConfigEntry
from .const import DOMAIN
from .store.model import LocalFolder, LocalFile, Node

_LOGGER = logging.getLogger(__name__)


class SupernoteIdentifierType(StrEnum):
    """Type for a SupernoteIdentifier."""

    NOTE_FILE = "f"
    NOTE_PAGE = "p"
    FOLDER = "f"

    @classmethod
    def of(cls, name: str) -> SupernoteIdentifierType:
        """Parse a SupernoteIdentifierType by string value."""
        for enum in SupernoteIdentifierType:
            if enum.value == name:
                return enum
        raise ValueError(f"Invalid SupernoteIdentifierType: {name}")


@dataclass
class SupernoteIdentifier:
    """Item identifier in a media source URL."""

    config_entry_id: str
    """Identifies the account for the media item."""

    id_type: SupernoteIdentifierType | None = None
    """Type of identifier"""

    media_id: int | None = None
    """Identifies the folder or file contents to show."""

    def as_string(self) -> str:
        """Serialize the identifier as a string."""
        if self.id_type is None:
            return self.config_entry_id
        return f"{self.config_entry_id}/{self.id_type}/{self.media_id}"

    @classmethod
    def of(cls, identifier: str) -> Self:
        """Parse a SupernoteIdentifier form a string."""
        parts = identifier.split("/")
        if len(parts) == 1:
            return cls(parts[0])
        if len(parts) != 3:
            raise BrowseError(f"Invalid identifier: {identifier}")
        return cls(parts[0], SupernoteIdentifierType.of(parts[1]), int(parts[2]))

    @classmethod
    def folder(cls, config_entry_id: str, folder_id: int) -> Self:
        """Create an album SupernoteIdentifier."""
        return cls(config_entry_id, SupernoteIdentifierType.FOLDER, folder_id)

    @classmethod
    def note_file(cls, config_entry_id: str, file_id: int) -> Self:
        """Create an album SupernoteIdentifier."""
        return cls(config_entry_id, SupernoteIdentifierType.NOTE_FILE, file_id)

    @classmethod
    def note_page(cls, config_entry_id: str, file_id: int, page_id: int) -> Self:
        """Create an album SupernoteIdentifier."""
        return cls(config_entry_id, SupernoteIdentifierType.NOTE_FILE, file_id)


async def async_get_media_source(hass: HomeAssistant) -> MediaSource:
    """Set up Supernote Cloud media source."""
    return SupernoteCloudMediaSource(hass)


class SupernoteCloudMediaSource(MediaSource):
    """Provide Supernote Cloud as media sources."""

    name = "Supernote Cloud"

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize Supernote Cloud source."""
        super().__init__(DOMAIN)
        self.hass = hass

    # async def async_resolve_media(self, item: MediaSourceItem) -> PlayMedia:
    #     """Resolve media identifier to a url.

    #     This will resolve a specific media item to a url for the full photo or video contents.
    #     """
    #     try:
    #         identifier = SupernoteIdentifier.of(item.identifier)
    #     except ValueError as err:
    #         raise BrowseError(f"Could not parse identifier: {item.identifier}") from err
    #     if (
    #         identifier.media_id is None
    #         or identifier.id_type != SupernoteIdentifierType.PHOTO
    #     ):
    #         raise BrowseError(
    #             f"Could not resolve identiifer that is not a Photo: {identifier}"
    #         )
    #     entry = self._async_config_entry(identifier.config_entry_id)
    #     client = entry.runtime_data.client
    #     media_item = await client.get_media_item(media_item_id=identifier.media_id)
    #     if not media_item.mime_type:
    #         raise BrowseError("Could not determine mime type of media item")
    #     if media_item.media_metadata and (media_item.media_metadata.video is not None):
    #         url = _video_url(media_item)
    #     else:
    #         url = _media_url(media_item, LARGE_IMAGE_SIZE)
    #     return PlayMedia(
    #         url=url,
    #         mime_type=media_item.mime_type,
    #     )

    async def async_browse_media(self, item: MediaSourceItem) -> BrowseMediaSource:
        """Return details about the media source.

        This renders the multi-level album structure for an account, its folders,
        or the contents of a note. This will return a BrowseMediaSource with a
        single level of children at the next level of the hierarchy.
        """
        if not item.identifier:
            # Top level view that lists all accounts.
            return BrowseMediaSource(
                domain=DOMAIN,
                identifier=None,
                media_class=MediaClass.DIRECTORY,
                media_content_type=MediaClass.IMAGE,
                title="Supernote Cloud",
                can_play=False,
                can_expand=True,
                children_media_class=MediaClass.DIRECTORY,
                children=[
                    _build_account(
                        entry, SupernoteIdentifier(cast(str, entry.unique_id))
                    )
                    for entry in self._async_config_entries()
                ],
            )

        # Determine the configuration entry for this item
        identifier = SupernoteIdentifier.of(item.identifier)
        entry = self._async_config_entry(identifier.config_entry_id)
        store = entry.runtime_data

        source = _build_account(entry, identifier)
        if identifier.id_type is None or SupernoteIdentifierType.FOLDER:
            media_id = 0 if identifier.id_type is None else identifier.media_id
            children = await store.get_children(media_id)
            source.children = [
                _build_item(child, identifier.config_entry_id) for child in children
            ]
            return source

        # if (
        #     identifier.id_type != SupernoteIdentifierType.ALBUM
        #     or identifier.media_id is None
        # ):
        #     raise BrowseError(f"Unsupported identifier: {identifier}")

        # media_items: list[MediaItem] = []
        # try:
        #     async for media_item_result in await client.list_media_items(
        #         album_id=identifier.media_id, page_size=MEDIA_ITEMS_PAGE_SIZE
        #     ):
        #         media_items.extend(media_item_result.media_items)
        # except SupernoteException as err:
        #     raise BrowseError(f"Error listing media items: {err}") from err

        # source.children = [
        #     _build_media_item(
        #         SupernoteIdentifier.photo(identifier.config_entry_id, media_item.id),
        #         media_item,
        #     )
        #     for media_item in media_items
        # ]
        # return source
        raise ValueError("done")

    def _async_config_entries(self) -> list[SupernoteCloudConfigEntry]:
        """Return all config entries that support photo library reads."""
        entries = []
        for entry in self.hass.config_entries.async_loaded_entries(DOMAIN):
            entries.append(entry)
        return entries

    def _async_config_entry(self, config_entry_id: str) -> SupernoteCloudConfigEntry:
        """Return a config entry with the specified id."""
        entry = self.hass.config_entries.async_entry_for_domain_unique_id(
            DOMAIN, config_entry_id
        )
        if not entry:
            raise BrowseError(
                f"Could not find config entry for identifier: {config_entry_id}"
            )
        return entry  # type: ignore[no-any-return]


def _build_account(
    config_entry: SupernoteCloudConfigEntry,
    identifier: SupernoteIdentifier,
) -> BrowseMediaSource:
    """Build the root node for a Supernote Cloud account for a config entry."""
    return BrowseMediaSource(
        domain=DOMAIN,
        identifier=identifier.as_string(),
        media_class=MediaClass.DIRECTORY,
        media_content_type=MediaClass.IMAGE,
        title=config_entry.title,
        can_play=False,
        can_expand=True,
    )


def _build_item(node: Node, config_entry_id: str) -> BrowseMediaSource:
    """Build an album node."""
    if isinstance(node, LocalFolder):
        return BrowseMediaSource(
            domain=DOMAIN,
            identifier=SupernoteIdentifier.folder(
                config_entry_id, node.folder_id
            ).as_string(),
            media_class=MediaClass.ALBUM,
            media_content_type=MediaClass.ALBUM,
            title=node.name,
            can_play=False,
            can_expand=True,
        )
    if not isinstance(node, LocalFile):
        raise ValueError(f"Unsupported node type: {node}")
    return BrowseMediaSource(
        domain=DOMAIN,
        identifier=SupernoteIdentifier.note_file(
            config_entry_id, node.file_id
        ).as_string(),
        media_class=MediaClass.APP,
        media_content_type=MediaType.APP,
        title=node.name,
        can_play=False,
        can_expand=False,
    )


# def _build_media_item(
#     identifier: SupernoteIdentifier,
#     media_item: MediaItem,
# ) -> BrowseMediaSource:
#     """Build the node for an individual photo or video."""
#     is_video = media_item.media_metadata and (
#         media_item.media_metadata.video is not None
#     )
#     return BrowseMediaSource(
#         domain=DOMAIN,
#         identifier=identifier.as_string(),
#         media_class=MediaClass.IMAGE if not is_video else MediaClass.VIDEO,
#         media_content_type=MediaType.IMAGE if not is_video else MediaType.VIDEO,
#         title=media_item.filename,
#         can_play=is_video,
#         can_expand=False,
#     )


# def _media_url(media_item: MediaItem, max_size: int) -> str:
#     """Return a media item url with the specified max thumbnail size on the longest edge.

#     See https://developers.google.com/photos/library/guides/access-media-items#base-urls
#     """
#     return f"{media_item.base_url}=h{max_size}"


# def _video_url(media_item: MediaItem) -> str:
#     """Return a video url for the item.

#     See https://developers.google.com/photos/library/guides/access-media-items#base-urls
#     """
#     return f"{media_item.base_url}=dv"


# def _cover_photo_url(album: Album, max_size: int) -> str:
#     """Return a media item url for the cover photo of the album."""
#     return f"{album.cover_photo_base_url}=h{max_size}"
