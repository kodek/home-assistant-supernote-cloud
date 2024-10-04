"""Local backup storage of Supernote Cloud data."""

import asyncio
import io
import datetime
import pathlib
import logging
from dataclasses import dataclass, field
from typing import cast

import supernotelib

from ..supernote_client.auth import SupernoteCloudClient
from .model import LocalFolder, LocalFile, Node

_LOGGER = logging.getLogger(__name__)


MAX_CACHE_LIFETIME = datetime.timedelta(hours=1)
NOTE_SUFFIX = ".note"
METADATA_SUFFIX = ".meta.json"
PNG_SUFFIX = ".png"
POLICY = "loose"


@dataclass(kw_only=True)
class CacheEntry:
    """A cache entry."""

    node: LocalFile | None = None
    children: list[Node] = field(default_factory=list)
    timestamp: datetime.datetime = field(default_factory=datetime.datetime.now)


class LocalStore:
    """Local storage of Supernote Cloud data."""

    def __init__(self, storage_path: pathlib.Path, client: SupernoteCloudClient):
        """Initialize the store."""
        self._storage_path = storage_path
        self._client = client
        self._folder_cache: dict[int, CacheEntry] = {}  # directory id -> cache entry
        self._file_cache: dict[int, CacheEntry] = {}  # file id -> cache entry

    async def get_children(self, folder_id: int) -> list[Node]:
        """Sync the local store with the cloud."""
        if folder_id in self._folder_cache:
            cache_entry = self._folder_cache[folder_id]
            if (datetime.datetime.now() - cache_entry.timestamp) < MAX_CACHE_LIFETIME:
                return cache_entry.children

        # Fetch the folder from the cloud
        file_list_response = await self._client.file_list(folder_id)
        nodes: list[Node] = []
        for file in file_list_response.file_list:
            if file.is_folder == "Y":
                new_folder = LocalFolder(
                    folder_id=file.id,
                    parent_folder_id=file.directory_id,
                    name=file.file_name,
                    create_time=file.create_time,
                    update_time=file.update_time,
                )
                nodes.append(new_folder)
            else:
                new_file = LocalFile(
                    file_id=file.id,
                    parent_folder_id=file.directory_id,
                    name=file.file_name,
                    md5=file.md5,
                    size=file.size,
                    create_time=file.create_time,
                    update_time=file.update_time,
                )
                self._file_cache[file.id] = CacheEntry(node=new_file)
                nodes.append(new_file)

        # Update the cache
        self._folder_cache[folder_id] = CacheEntry(children=nodes)
        return nodes

    async def get_local_file(self, file_id: int) -> LocalFile:
        """Sync the local store with the cloud."""
        if file_id in self._file_cache:
            cache_entry = self._file_cache[file_id]
            if not cache_entry.node:
                raise ValueError("Invalid file node, did not have node contents")
            return cache_entry.node
        raise ValueError("File not found")

    async def get_note_pages(self, local_file: LocalFile) -> int:
        """Get the number of pages for a note file."""

        note_contents = await self._get_note(local_file)
        notebook = supernotelib.load(io.BytesIO(note_contents), policy=POLICY)
        return int(notebook.get_total_pages())

    async def get_note_png(self, local_file: LocalFile, page_num: int) -> bytes:
        """Get the PNG contents of a note file."""

        note_contents = await self._get_note(local_file)

        # If a png version of the note file does not exist, call the conversion
        # function on the note file on the fly and persit.
        local_path = self._get_local_file_path(local_file)
        local_png_path = local_path.with_suffix(PNG_SUFFIX)

        def _read_png() -> bytes | None:
            if local_png_path.exists():
                with local_png_path.open("rb") as png_file:
                    return png_file.read()
            return None

        loop = asyncio.get_running_loop()
        contents = await loop.run_in_executor(None, _read_png)
        if contents:
            return contents

        # Convert the note file to a PNG file
        notebook = supernotelib.load(io.BytesIO(note_contents), policy=POLICY)
        converter = supernotelib.converter.ImageConverter(notebook)
        page_id = notebook.get_page(page_num).get_pageid()
        content = converter.convert(page_id)
        content.save(str(local_png_path), format="PNG")

        contents = await loop.run_in_executor(None, _read_png)
        if not contents:
            raise ValueError("Failed to convert note to PNG")
        return contents

    def _get_local_file_path(self, local_file: LocalFile) -> pathlib.Path:
        parent = self._storage_path / str(local_file.parent_folder_id)
        # Read the existing metadata for the note file and see if the content
        # is already cached on local disk.
        return parent / local_file.name

    async def _get_note(self, local_file: LocalFile) -> bytes:
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
                    existing_metadata = LocalFile.from_json(metadata_file.read())
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
