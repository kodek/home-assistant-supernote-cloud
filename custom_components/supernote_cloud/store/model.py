"""Data model for local Supernote Backups."""

import datetime
from dataclasses import dataclass, field

from mashumaro.mixins.json import DataClassJSONMixin


MAX_CACHE_LIFETIME = datetime.timedelta(hours=1)


@dataclass
class FileInfo(DataClassJSONMixin):
    """Representation of a file."""

    file_id: int
    parent_folder_id: int
    name: str
    md5: str
    size: int
    create_time: int
    update_time: int


@dataclass
class FolderInfo(DataClassJSONMixin):
    """A folder in a Supernote backup."""

    folder_id: int
    parent_folder_id: int
    name: str
    create_time: int | None = None
    update_time: int | None = None


@dataclass
class FolderContents(DataClassJSONMixin):
    """A folder in a Supernote backup."""

    folder_id: int
    file_children: list[FileInfo] = field(default_factory=list)
    folder_children: list[FolderInfo] = field(default_factory=list)

    cache_ts: datetime.datetime = field(default_factory=datetime.datetime.now)

    @property
    def is_expired(self) -> bool:
        """Check if the cache is expired."""
        return (datetime.datetime.now() - self.cache_ts) > MAX_CACHE_LIFETIME

    @property
    def children(self) -> dict[int, FileInfo | FolderInfo]:
        """Get the children of the folder."""
        children: dict[int, FileInfo | FolderInfo] = {}
        for file in self.file_children:
            children[file.file_id] = file
        for folder in self.folder_children:
            children[folder.folder_id] = folder
        return children
