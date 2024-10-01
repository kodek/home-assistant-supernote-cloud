"""Data model for local Supernote Backups."""

from dataclasses import dataclass
from typing import Self

from mashumaro.mixins.json import DataClassJSONMixin


@dataclass(kw_only=True)
class Node(DataClassJSONMixin):
    """A folder in a Supernote backup."""

    children: list[Self] = []


@dataclass(kw_only=True)
class LocalFile(Node):
    """Representation of a file."""

    file_id: int
    parent_folder_id: int
    name: str
    md5: str
    size: int
    create_time: int
    update_time: int


@dataclass(kw_only=True)
class LocalFolder(Node):
    """A folder in a Supernote backup."""

    folder_id: int
    parent_folder_id: int | None = None
    name: str
    create_time: int | None = None
    update_time: int | None = None
