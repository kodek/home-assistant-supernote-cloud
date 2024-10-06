"""Local backup storage of Supernote Cloud data."""

from __future__ import annotations

import asyncio
import io
import pathlib
import logging
from typing import cast

import supernotelib

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from ..supernote_client.auth import SupernoteCloudClient
from .model import FolderContents, FileInfo, FolderInfo

_LOGGER = logging.getLogger(__name__)


NOTE_SUFFIX = ".note"
METADATA_SUFFIX = ".meta.json"
PNG_SUFFIX = ".png"
POLICY = "loose"
STORAGE_KEY = "supernote_cloud"
STORAGE_VERSION = 1


class MetadataStore:
    """Local storage of metadata for Supernote Cloud data.

    This is essentially a cache of the API responses to avoid putting load
    on cloud when reading backups.
    """

    def __init__(self, hass: HomeAssistant, storage_path: pathlib.Path) -> None:
        """Initialize the store."""
        self._store = Store(
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
        metadata_store: MetadataStore,
        storage_path: pathlib.Path,
        client: SupernoteCloudClient,
    ):
        """Initialize the store."""
        self._metadata_store = metadata_store
        self._storage_path = storage_path
        self._client = client

    async def get_folder_contents(self, folder_id: int) -> FolderContents:
        """Fetch the folder information."""

        folder_contents = await self._metadata_store.get_folder_contents(folder_id)
        if folder_contents and not folder_contents.is_expired:
            _LOGGER.debug("Serving %s from local cache %s", folder_id, folder_contents)
            return folder_contents

        # Fetch the folder from the cloud
        file_list_response = await self._client.file_list(folder_id)
        folder_contents = FolderContents(folder_id=folder_id)
        for file in file_list_response.file_list:
            if file.is_folder == "Y":
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

        # Update the cache
        _LOGGER.debug("Updating cache for %s", folder_contents)
        await self._metadata_store.set_folder_contents(folder_contents)

        return folder_contents

    async def get_note_pages(self, local_file: FileInfo) -> int:
        """Get the number of pages for a note file."""

        note_contents = await self._get_note(local_file)
        notebook = supernotelib.load(io.BytesIO(note_contents), policy=POLICY)
        return int(notebook.get_total_pages())

    async def get_note_png(self, local_file: FileInfo, page_num: int) -> bytes:
        """Get the PNG contents of a note file."""

        note_contents = await self._get_note(local_file)
        notebook = supernotelib.load(io.BytesIO(note_contents), policy=POLICY)
        page_id = notebook.get_page(page_num).get_pageid()

        # If a png version of the note file does not exist, call the conversion
        # function on the note file on the fly and persit.
        local_path = self._get_local_file_path(local_file)
        local_png_path = (local_path.with_suffix("") / f"{page_num}-{page_id}").with_suffix(PNG_SUFFIX)

        def _read_png() -> bytes | None:
            local_png_path.parent.mkdir(exist_ok=True)
            if local_png_path.exists():
                with local_png_path.open("rb") as png_file:
                    return png_file.read()
            return None

        loop = asyncio.get_running_loop()
        contents = await loop.run_in_executor(None, _read_png)
        if contents:
            return contents

        converter = supernotelib.converter.ImageConverter(notebook)
        content = converter.convert(page_num)
        content.save(str(local_png_path), format="PNG")

        contents = await loop.run_in_executor(None, _read_png)
        if not contents:
            raise ValueError("Failed to convert note to PNG")
        return contents

    def _get_local_file_path(self, local_file: FileInfo) -> pathlib.Path:
        parent = self._storage_path / str(local_file.parent_folder_id)
        # Read the existing metadata for the note file and see if the content
        # is already cached on local disk.
        return parent / local_file.name

    async def _get_note(self, local_file: FileInfo) -> bytes:
        """Get the contents of a note file."""
        if not local_file.name.endswith(NOTE_SUFFIX):
            raise ValueError("Cannot get pages for non-note file")

        local_path = self._get_local_file_path(local_file)
        local_metadata_path = local_path.with_suffix(METADATA_SUFFIX)

        def _get_or_invalidate() -> bytes | None:
            local_path.parent.mkdir(exist_ok=True)

            # Read the existing metadata for the note file and see if the content
            # is already cached on local disk.
            if local_metadata_path.exists():
                with local_metadata_path.open("r") as metadata_file:
                    existing_metadata = FileInfo.from_json(metadata_file.read())
                    if existing_metadata.md5 == local_file.md5:
                        with local_path.open("rb") as note_file:
                            _LOGGER.debug(
                                "Serving %s from local cache", local_file.name
                            )
                            return note_file.read()
                    else:
                        _LOGGER.debug("MD5 updated for %s", local_file.name)

                # Erase any existing metadata contents since they are no longer up
                # to date.
                local_metadata_path.unlink(missing_ok=True)
            return None

        loop = asyncio.get_running_loop()
        contents = await loop.run_in_executor(None, _get_or_invalidate)
        if contents:
            return contents

        _LOGGER.debug("Downloading %s", local_file.name)
        contents = await self._client.file_download(local_file.file_id)

        def _write_contents() -> None:
            with local_path.open("wb") as note_file:
                note_file.write(contents)

            # Write the metadata
            with local_metadata_path.open("w") as metadata_file:
                metadata_file.write(cast(str, local_file.to_json()))

        await loop.run_in_executor(None, _write_contents)

        return contents
