"""Local backup storage of Supernote Cloud data."""

import datetime
import pathlib
from dataclasses import dataclass, field
from typing import cast

from ..supernote_client.auth import SupernoteCloudClient
from .model import LocalFolder, LocalFile, Node


MAX_CACHE_LIFETIME = datetime.timedelta(hours=1)
NOTE_SUFFIX = ".note"
METADATA_SUFFIX = ".meta.json"
PNG_SUFFIX = ".png"


@dataclass(kw_only=True)
class CacheEntry:
    """A cache entry."""

    nodes: list[Node]
    timestamp: datetime.datetime = field(default_factory=datetime.datetime.now)


class LocalStore:
    """Local storage of Supernote Cloud data."""

    def __init__(self, storage_path: pathlib.Path, client: SupernoteCloudClient):
        """Initialize the store."""
        self._storage_path = storage_path
        self._client = client
        self._folder_cache: dict[int, CacheEntry] = {}  # directory id -> cache entry

    async def get_children(self, folder_id: int) -> list[Node]:
        """Sync the local store with the cloud."""
        if folder_id in self._folder_cache:
            cache_entry = self._folder_cache[folder_id]
            if (datetime.datetime.now() - cache_entry.timestamp) < MAX_CACHE_LIFETIME:
                return cache_entry.nodes

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
                nodes.append(new_file)

        # Update the cache
        self._folder_cache[folder_id] = CacheEntry(nodes=nodes)
        return nodes

    async def get_note_png(self, local_file: LocalFile) -> bytes:
        """Get the PNG contents of a note file."""
        if not local_file.name.endswith(NOTE_SUFFIX):
            raise ValueError("Cannot get PNG for non-note file")

        parent = self._storage_path / str(local_file.parent_folder_id)
        if not parent.exists():
            parent.mkdir(parents=True, exist_ok=True)

        # Read the existing metadata for the note file and see if the content
        # is already cached on local disk.
        local_path = parent / local_file.name
        local_png_path = local_path.with_suffix(PNG_SUFFIX)
        local_metadata_path = local_path.with_suffix(METADATA_SUFFIX)
        if local_metadata_path.exists():
            with local_metadata_path.open("r") as metadata_file:
                existing_metadata = LocalFile.from_json(metadata_file.read())
                if existing_metadata.md5 == local_file.md5:
                    with local_png_path.open("rb") as png_file:
                        return png_file.read()

            # Erase any existing metadata contents since they are no longer up
            # to date.
            local_metadata_path.unlink(missing_ok=True)

        contents = await self._client.file_download(local_file.file_id)
        with local_png_path.open("wb") as png_file:
            png_file.write(contents)

        # Write the metadata
        with local_metadata_path.open("w") as metadata_file:
            metadata_file.write(cast(str, local_file.to_json()))

        return contents
