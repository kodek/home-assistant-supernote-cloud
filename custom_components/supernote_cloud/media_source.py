"""Media source for viewing local copies of Supernote media."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import logging
from typing import Self, cast

from aiohttp.web import Response, Request, StreamResponse

from homeassistant.components.http.view import HomeAssistantView
from homeassistant.components.media_player import MediaClass, MediaType
from homeassistant.components.media_source import (
    BrowseError,
    BrowseMediaSource,
    MediaSource,
    MediaSourceItem,
    PlayMedia,
)
from homeassistant.core import HomeAssistant, callback

from . import SupernoteCloudConfigEntry
from .const import DOMAIN
from .store.model import FileInfo, FolderInfo

_LOGGER = logging.getLogger(__name__)


class SupernoteIdentifierType(StrEnum):
    """Type for a SupernoteIdentifier."""

    NOTE_FILE = "n"
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

    id_type: SupernoteIdentifierType
    """Type of identifier"""

    media_id_path: list[int]
    """Identifies the folder or file contents to show."""

    @property
    def is_root(self) -> bool:
        """Return True if this is the root node."""
        return len(self.media_id_path) == 1

    @property
    def media_id(self) -> int:
        """Return the leaf media id for the identifier."""
        return self.media_id_path[-1]

    @property
    def parent_folder_id(self) -> int | None:
        """Return the parent node media id for the identifier."""
        if self.id_type == SupernoteIdentifierType.NOTE_PAGE:
            if len(self.media_id_path) < 3:
                raise ValueError(
                    f"Invalid note page identifier did not contain a parent folder id: {self}"
                )
            return self.media_id_path[-3]
        if len(self.media_id_path) < 2:
            return None
        return self.media_id_path[-2]

    @property
    def note_file_id(self) -> int | None:
        """Return the note file id for a NOTE_PAGE identifier."""
        if self.id_type == SupernoteIdentifierType.NOTE_FILE:
            return self.media_id
        if self.id_type != SupernoteIdentifierType.NOTE_PAGE:
            return None
        if len(self.media_id_path) < 2:
            raise ValueError(
                f"Invalid note page identifier did not contain a note file id: {self}"
            )
        return self.media_id_path[-2]

    @property
    def page_id(self) -> int | None:
        """Return the page id for a NOTE_PAGE identifier."""
        if self.id_type != SupernoteIdentifierType.NOTE_PAGE:
            return None
        if len(self.media_id_path) < 3:
            raise ValueError(
                f"Invalid note page identifier did not contain a page id: {self}"
            )
        return self.media_id_path[-1]

    def as_string(self, separator: str = "/") -> str:
        """Serialize the identifier as a string."""
        path_parts = separator.join(str(part) for part in self.media_id_path)
        return f"{self.config_entry_id}{separator}{self.id_type}{separator}{path_parts}"

    @classmethod
    def of(cls, identifier: str, separator: str = "/") -> Self:
        """Parse a SupernoteIdentifier form a string."""
        parts = identifier.split(separator, maxsplit=2)
        if len(parts) != 3:
            raise ValueError(f"Invalid identifier: {identifier}")
        try:
            path_parts = [int(p) for p in parts[2].split(separator)]
        except ValueError as err:
            raise ValueError(f"Invalid identifier: {identifier}") from err
        return cls(parts[0], SupernoteIdentifierType.of(parts[1]), path_parts)

    def encode(self) -> str:
        """Serialize the identifier as a url string."""
        return self.as_string(":")

    @classmethod
    def decode(cls, identifier: str) -> Self:
        """Parse a SupernoteIdentifier form a url string."""
        return cls.of(identifier, ":")

    @classmethod
    def folder(cls, config_entry_id: str, media_ids: list[int]) -> Self:
        """Create an album SupernoteIdentifier."""
        return cls(config_entry_id, SupernoteIdentifierType.FOLDER, media_ids)

    @classmethod
    def note_file(cls, config_entry_id: str, media_ids: list[int]) -> Self:
        """Create an album SupernoteIdentifier."""
        return cls(config_entry_id, SupernoteIdentifierType.NOTE_FILE, media_ids)

    @classmethod
    def note_page(cls, config_entry_id: str, media_ids: list[int]) -> Self:
        """Create an album SupernoteIdentifier."""
        return cls(config_entry_id, SupernoteIdentifierType.NOTE_PAGE, media_ids)


@callback
def async_register_http_views(hass: HomeAssistant) -> None:
    """Register the http views."""
    hass.http.register_view(ItemContentView(hass))


class ItemContentView(HomeAssistantView):
    """Returns media content for a specific media source item."""

    url = "/api/supernote_cloud/item_content/{item_identifier}"
    name = "api:supernote_cloud:item_content"

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the view."""
        self.hass = hass

    async def get(self, request: Request, item_identifier: str) -> StreamResponse:
        """Start a GET request."""
        try:
            identifier = SupernoteIdentifier.decode(item_identifier)
        except ValueError as err:
            _LOGGER.error("Invalid identifier: %s", item_identifier)
            return Response(status=400, text=str(err))

        _LOGGER.debug("Fetching item content for %s", identifier)
        if identifier.id_type != SupernoteIdentifierType.NOTE_PAGE:
            msg = f"Invalid identifier type: {identifier}"
            _LOGGER.error(msg)
            return Response(status=400, text=msg)

        if (
            entry := self.hass.config_entries.async_entry_for_domain_unique_id(
                DOMAIN,
                identifier.config_entry_id,
            )
        ) is None:
            msg = f"Could not find config entry for identifier: {identifier.config_entry_id}"
            _LOGGER.error(msg)
            return Response(status=400, text=msg)
        store = entry.runtime_data

        folder_contents = await store.get_folder_contents(identifier.parent_folder_id)
        if folder_contents is None:
            msg = f"Could not find folder contents for {identifier}"
            _LOGGER.error(msg)
            return Response(status=400, text=msg)
        if (file_info := folder_contents.children.get(identifier.note_file_id)) is None:
            msg = f"Could not find file {identifier.note_file_id} in parent {identifier.parent_folder_id}"
            _LOGGER.error(msg)
            return Response(status=400, text=msg)

        content = await store.get_note_png(file_info, identifier.page_id)
        return Response(body=content, content_type="image/png")


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

    async def async_resolve_media(self, item: MediaSourceItem) -> PlayMedia:
        """Resolve media identifier to a note page url."""
        try:
            identifier = SupernoteIdentifier.of(item.identifier)
        except ValueError as err:
            raise BrowseError(f"Could not parse identifier: {item.identifier}") from err
        return PlayMedia(
            url=ItemContentView.url.format(item_identifier=identifier.encode()),
            mime_type="image/png",
        )

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
                        entry,
                        SupernoteIdentifier.folder(cast(str, entry.unique_id), [0]),
                    )
                    for entry in self._async_config_entries()
                ],
            )

        # Determine the configuration entry for this item
        try:
            identifier = SupernoteIdentifier.of(item.identifier)
        except ValueError as err:
            raise BrowseError(f"Could not parse identifier: {item.identifier}") from err
        _LOGGER.debug("Browsing media for %s", identifier)
        if identifier.id_type is None:
            raise BrowseError(
                f"Invalid identifier did not contain an id type: {identifier}"
            )

        entry = self._async_config_entry(identifier.config_entry_id)
        entry_unique_id = cast(str, entry.unique_id)
        store = entry.runtime_data

        if identifier.id_type is SupernoteIdentifierType.FOLDER:
            if not len(identifier.media_id_path):
                raise BrowseError(
                    f"Invalid identifier did not contain a media id: {identifier}"
                )

            # Create the node for the parent folder
            if identifier.is_root:
                source = _build_account(entry, identifier)
            else:
                if identifier.parent_folder_id is None:
                    raise BrowseError(
                        f"Invalid identifier did not contain a parent folder id: {identifier}"
                    )
                parent_folder_contents = await store.get_folder_contents(
                    identifier.parent_folder_id
                )
                _LOGGER.debug("Contents: %s", parent_folder_contents)
                if (
                    folder_info := parent_folder_contents.children.get(
                        identifier.media_id
                    )
                ) is None:
                    raise BrowseError(
                        f"Could not find folder {identifier.media_id} in parent {identifier.parent_folder_id}"
                    )
                if not isinstance(folder_info, FolderInfo):
                    raise BrowseError(f"Expected folder but got {folder_info}")
                source = _build_folder(
                    entry_unique_id,
                    identifier.parent_folder_id,
                    folder_info.folder_id,
                    folder_info.name,
                )

            # Add the children of the folder
            folder_contents = await store.get_folder_contents(identifier.media_id)
            children = []
            for child in folder_contents.children.values():
                _LOGGER.debug("Child: %s", child)
                if isinstance(child, FileInfo):
                    children.append(
                        _build_file(
                            entry_unique_id,
                            identifier.media_id,
                            child.file_id,
                            child.name,
                        )
                    )
                elif isinstance(child, FolderInfo):
                    children.append(
                        _build_folder(
                            entry_unique_id,
                            identifier.media_id,
                            child.folder_id,
                            child.name,
                        )
                    )
                else:
                    raise ValueError(f"Unexpected child type: {child}")
            source.children = children
            return source

        if identifier.id_type is SupernoteIdentifierType.NOTE_PAGE:
            raise ValueError("Cannot browse note pages")

        if identifier.parent_folder_id is None:
            raise ValueError("Cannot browse root folder as a note")

        # We are browsing a note file
        parent_folder_contents = await store.get_folder_contents(
            identifier.parent_folder_id
        )
        if (
            file_info := parent_folder_contents.children.get(identifier.media_id)
        ) is None:
            raise BrowseError(
                f"Could not find note file {identifier.media_id} in parent {identifier.parent_folder_id}"
            )
        if not isinstance(file_info, FileInfo):
            raise BrowseError(f"Expected file but got {file_info}")

        source = _build_file(
            entry_unique_id,
            identifier.parent_folder_id,
            file_info.file_id,
            file_info.name,
        )
        num_pages = await store.get_note_pages(file_info)
        _LOGGER.debug("Note has %s pages", num_pages)
        source.children = [
            BrowseMediaSource(
                domain=DOMAIN,
                identifier=SupernoteIdentifier.note_page(
                    identifier.config_entry_id,
                    [identifier.parent_folder_id, identifier.media_id, page],
                ).as_string(),
                media_class=MediaClass.APP,
                media_content_type=MediaType.APP,
                title=f"Page {page + 1}",
                can_play=True,
                can_expand=False,
            )
            for page in range(0, num_pages)
        ]
        return source

    def _async_config_entries(self) -> list[SupernoteCloudConfigEntry]:
        """Return all config entries that support photo library reads."""
        entries = []
        for entry in self.hass.config_entries.async_loaded_entries(DOMAIN):
            entries.append(entry)
        return entries

    def _async_config_entry(self, config_entry_id: str) -> SupernoteCloudConfigEntry:
        """Return a config entry with the specified id."""
        entry = self.hass.config_entries.async_entry_for_domain_unique_id(
            DOMAIN,
            config_entry_id,
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


def _build_folder(
    config_entry_id: str, parent_folder_id: int, folder_id: int, name: str
) -> BrowseMediaSource:
    """Build a media item node for a folder."""
    return BrowseMediaSource(
        domain=DOMAIN,
        identifier=SupernoteIdentifier.folder(
            config_entry_id,
            [parent_folder_id, folder_id],
        ).as_string(),
        media_class=MediaClass.APP,
        media_content_type=MediaType.APP,
        title=name,
        can_play=False,
        can_expand=True,
    )


def _build_file(
    config_entry_id: str, parent_folder_id: int, file_id: int, name: str
) -> BrowseMediaSource:
    """Build a media item node for a file."""
    return BrowseMediaSource(
        domain=DOMAIN,
        identifier=SupernoteIdentifier.note_file(
            config_entry_id,
            [parent_folder_id, file_id],
        ).as_string(),
        media_class=MediaClass.ALBUM,
        media_content_type=MediaClass.ALBUM,
        title=name,
        can_play=False,
        can_expand=True,
    )
