"""Local backup storage of Supernote Cloud data."""

from __future__ import annotations

import asyncio
import io
import pathlib
import logging
import hashlib
from typing import Any
from collections.abc import Callable
from abc import ABC, abstractmethod

import supernote
import supernote.parser
import supernote.converter

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from ..supernote_client.auth import SupernoteCloudClient
from ..supernote_client.exceptions import UnauthorizedException
from .model import FolderContents, FileInfo, FolderInfo, IS_FOLDER

_LOGGER = logging.getLogger(__name__)


NOTE_SUFFIX = ".note"
METADATA_SUFFIX = ".meta.json"
PNG_SUFFIX = ".png"
POLICY = "loose"
STORAGE_KEY = "supernote_cloud"
STORAGE_VERSION = 1


class AbstractMetadataStore(ABC):
    """Abstract class for local storage of metadata for Supernote Cloud data."""

    @abstractmethod
    async def get_folder_contents(self, folder_id: int) -> FolderContents | None:
        """Get the metadata for a local folder."""

    @abstractmethod
    async def set_folder_contents(self, folder: FolderContents) -> None:
        """Set the metadata for a local folder."""


class MetadataStore(AbstractMetadataStore):
    """Local storage of metadata for Supernote Cloud data.

    This is essentially a cache of the API responses to avoid putting load
    on cloud when reading backups.
    """

    def __init__(self, hass: HomeAssistant, storage_path: pathlib.Path) -> None:
        """Initialize the store."""
        self._store: Store[dict[str, Any]] = Store(
            hass,
            version=STORAGE_VERSION,
            key=str(storage_path / "folder_contents.json"),
            private=True,
        )

    async def get_folder_contents(self, folder_id: int) -> FolderContents | None:
        """Get the metadata for a local folder."""
        data = await self._store.async_load() or {}
        if (metadata := data.get(str(folder_id))) is None:
            return None
        return FolderContents.from_dict(metadata)

    async def set_folder_contents(self, folder: FolderContents) -> None:
        """Set the metadata for a local folder."""
        data = await self._store.async_load() or {}
        data[str(folder.folder_id)] = folder.to_dict()
        await self._store.async_save(data)


class LocalStore:
    """Local storage of Supernote Cloud data."""

    def __init__(
        self,
        metadata_store: AbstractMetadataStore,
        storage_path: pathlib.Path,
        client: SupernoteCloudClient,
        reauth_cb: Callable[[], None],
    ) -> None:
        """Initialize the store."""
        self._metadata_store = metadata_store
        self._storage_path = storage_path
        self._client = client
        self._reauth_cb = reauth_cb

    async def get_folder_contents(self, folder_id: int) -> FolderContents:
        """Fetch the folder information."""

        folder_contents = await self._metadata_store.get_folder_contents(folder_id)
        if folder_contents and not folder_contents.is_expired:
            _LOGGER.debug("Serving %s from local cache", folder_id)
            return folder_contents

        # Fetch the folder from the cloud
        try:
            file_list_response = await self._client.file_list(folder_id)
        except UnauthorizedException as err:
            self._reauth_cb()
            raise err
        folder_contents = FolderContents(folder_id=folder_id)
        for file in file_list_response.file_list:
            if file.is_folder == IS_FOLDER:
                new_folder = FolderInfo(
                    folder_id=file.id,
                    parent_folder_id=file.directory_id,
                    name=file.file_name,
                    create_time=file.create_time,
                    update_time=file.update_time,
                )
                folder_contents.folder_children.append(new_folder)
            else:
                new_file = FileInfo(
                    file_id=file.id,
                    parent_folder_id=file.directory_id,
                    name=file.file_name,
                    md5=file.md5,
                    size=file.size,
                    create_time=file.create_time,
                    update_time=file.update_time,
                )
                folder_contents.file_children.append(new_file)

        _LOGGER.debug("Updating cache for %s", folder_contents)
        await self._metadata_store.set_folder_contents(folder_contents)

        return folder_contents

    async def get_note_page_names(self, local_file: FileInfo) -> list[str]:
        """Get the names of each page of the note file."""
        notebook = await self._get_notebook_file(local_file)
        return notebook.page_names

    async def get_note_png(self, local_file: FileInfo, page_num: int) -> bytes:
        """Get the PNG contents of a note file."""

        notebook = await self._get_notebook_file(local_file)

        # If a png version of the note file does not exist, call the conversion
        # function on the note file on the fly and persit.
        if (contents := await notebook.read_png(page_num)) is not None:
            return contents

        await notebook.save_page_png(page_num)

        contents = await notebook.read_png(page_num)
        if not contents:
            raise ValueError("Failed to convert note to PNG")
        return contents

    def _get_local_file_path(self, local_file: FileInfo) -> pathlib.Path:
        parent = self._storage_path / str(local_file.parent_folder_id)
        # Read the existing metadata for the note file and see if the content
        # is already cached on local disk.
        return parent / local_file.name

    async def _get_notebook_file(self, local_file: FileInfo) -> NotebookFile:
        """Get the contents of a note file."""
        if not local_file.name.endswith(NOTE_SUFFIX):
            raise ValueError("Cannot get pages for non-note file")

        local_path = self._get_local_file_path(local_file)
        _LOGGER.debug("Local path: %s", local_path)

        def _get_or_invalidate() -> bytes | None:
            local_path.parent.mkdir(exist_ok=True)

            # Read the existing metadata for the note file and see if the content
            # is already cached on local disk.
            if local_path.exists():
                with local_path.open("rb") as note_file:
                    contents = note_file.read()
                    md5sum = hashlib.md5(contents).hexdigest()
                    if md5sum == local_file.md5:
                        _LOGGER.debug("Serving %s from local cache", local_file.name)
                        return contents
                # The local file is out of date, invalidate it.
                local_path.unlink()
            return None

        loop = asyncio.get_running_loop()
        contents = await loop.run_in_executor(None, _get_or_invalidate)
        if contents:
            return NotebookFile(contents, local_file.name, local_path)

        _LOGGER.debug("Downloading %s", local_file.name)
        try:
            contents = await self._client.file_download(local_file.file_id)
        except UnauthorizedException as err:
            self._reauth_cb()
            raise err

        def _write_contents() -> None:
            with local_path.open("wb") as note_file:
                note_file.write(contents)

        await loop.run_in_executor(None, _write_contents)

        md5sum = hashlib.md5(contents).hexdigest()
        if md5sum != local_file.md5:
            _LOGGER.error(
                "Downloaded file had different hash from server (%s) != (%s)",
                md5sum,
                local_file.md5,
            )

        notebook = NotebookFile(contents, local_file.name, local_path)
        await notebook.clear_png_cache()
        return notebook


class NotebookFile:
    """Representation of a note file."""

    def __init__(
        self, note_contents: bytes, note_name: str, local_file_path: pathlib.Path
    ) -> None:
        """Initialize the notebook."""
        self._note_contents = note_contents
        self._local_file_path = local_file_path
        self._notebook = supernote.parser.load(io.BytesIO(note_contents), policy=POLICY)
        note_name_base = pathlib.Path(note_name).stem
        pages = []
        for page_num in range(self._notebook.get_total_pages()):
            page_id = self._notebook.get_page(page_num).get_pageid()
            page_name = f"{note_name_base}-{page_num:03d}-{page_id}"
            pages.append(page_name)
        self._pages = pages

    @property
    def contents(self) -> bytes:
        """Get the contents of the note file."""
        return self._note_contents

    @property
    def page_names(self) -> list[str]:
        """Get the names of each page of the note file."""
        return self._pages

    def local_png_path(self, page_num: int) -> pathlib.Path:
        if page_num >= len(self._pages) or page_num < 0:
            raise ValueError("Invalid page number")
        return (
            self._local_file_path.parent
            / self._local_file_path.stem
            / self._pages[page_num]
        ).with_suffix(PNG_SUFFIX)

    async def save_page_png(self, page_num: int) -> None:
        """Extract the PNG contents of a note file."""
        local_png_path = self.local_png_path(page_num)

        def _write_png() -> None:
            converter = supernote.converter.ImageConverter(self._notebook)
            content = converter.convert(page_num)
            content.save(str(local_png_path), format="PNG")

        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, _write_png)

    async def read_png(self, page_num: int) -> bytes | None:
        """Read the PNG contents of a note file."""
        local_png_path = self.local_png_path(page_num)

        def _read_png() -> bytes | None:
            local_png_path.parent.mkdir(exist_ok=True)
            if local_png_path.exists():
                with local_png_path.open("rb") as png_file:
                    return png_file.read()
            return None

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, _read_png)

    async def clear_png_cache(self) -> None:
        """Read the PNG contents of a note file."""

        def _clear_pngs() -> None:
            """All pngs  pages of the notebook."""
            for page_num in range(self._notebook.get_total_pages()):
                png_path = self.local_png_path(page_num)
                if png_path.exists():
                    png_path.unlink()

        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, _clear_pngs)
