"""Tests for the Supernote Cloud store."""

import pathlib
import tempfile
from unittest.mock import AsyncMock, MagicMock, Mock
from collections.abc import Generator

import pytest
from supernote.cloud.api_model import (
    FileListResponse,
    File,
)

from custom_components.supernote_cloud.store.store import (
    LocalStore,
    AbstractMetadataStore,
)
from custom_components.supernote_cloud.store.model import FolderContents, FileInfo

NOTE_FILE = pathlib.Path("tests/store/testdata/Guitar.note")


class FakeStore(AbstractMetadataStore):
    """Fake store for testing."""

    def __init__(self) -> None:
        """Initialize the store."""
        self._metadata = {}

    async def get_folder_contents(self, folder_id: int) -> FolderContents | None:
        """Get the metadata for a local folder."""
        return self._metadata.get(folder_id)

    async def set_folder_contents(self, folder: FolderContents) -> None:
        """Set the metadata for a local folder."""
        self._metadata[folder.folder_id] = folder


@pytest.fixture(name="metadata_store")
def metadata_store_fixture() -> FakeStore:
    """Create a fake metadata store."""
    return FakeStore()


@pytest.fixture(name="client")
def client_fixture() -> Mock:
    """Create a client."""
    return MagicMock()


@pytest.fixture(name="store_path")
def store_path_fixture() -> Generator[pathlib.Path]:
    """Create a store path."""
    with tempfile.TemporaryDirectory() as temp_file:
        yield pathlib.Path(temp_file)


@pytest.fixture(name="local_store")
def local_store_fixture(
    metadata_store: FakeStore, client: Mock, store_path: pathlib.Path
) -> LocalStore:
    """Create a local store."""
    return LocalStore(metadata_store, store_path, client, MagicMock())


@pytest.fixture(name="note_contents")
def note_contents_fixture() -> bytes:
    """Create note contents."""
    with NOTE_FILE.open("rb") as file:
        return file.read()


async def test_cached_folder_contents(
    metadata_store: FakeStore, local_store: LocalStore
) -> None:
    """Test getting folder contents."""

    folder = FolderContents(folder_id=1234)
    assert not folder.is_expired
    await metadata_store.set_folder_contents(folder)

    contents = await local_store.get_folder_contents(1234)
    assert contents == folder


async def test_folder_contents(
    metadata_store: FakeStore, local_store: LocalStore, client: Mock
) -> None:
    """Test getting folder contents."""

    client.file_list = AsyncMock()
    client.file_list.return_value = FileListResponse(
        success=True,
        total=1,
        size=1,
        pages=1,
        file_list=[
            File(
                id=1234,
                directory_id=0,
                file_name="file-1",
                size=0,
                md5="",
                is_folder="Y",
                create_time=0,
                update_time=0,
            )
        ],
    )

    contents = await local_store.get_folder_contents(1234)
    assert contents.folder_id == 1234
    assert len(contents.folder_children) == 1
    assert contents.folder_children[0].name == "file-1"


async def test_get_note_pages(
    client: Mock, local_store: LocalStore, note_contents: bytes
) -> None:
    """Test getting note page names and content."""

    local_file = FileInfo(
        file_id=1234,
        parent_folder_id=0,
        name="Guitar.note",
        md5="some-hash",
        size=5,
        create_time=0,
        update_time=0,
    )

    client.file_download = AsyncMock()
    client.file_download.return_value = note_contents

    result = await local_store.get_note_page_names(local_file)
    assert result == [
        "Guitar-000-P20231228174201877470DZj4cQ3c93Wi",
        "Guitar-001-P20240128210859017639qfzFJkp6gj2V",
    ]

    # We don't verify the actual page contents
    await local_store.get_note_png(local_file, 0)


async def test_get_note_pages_from_cache(
    client: Mock,
    local_store: LocalStore,
    store_path: pathlib.Path,
    note_contents: bytes,
) -> None:
    """Test getting note page names and content."""

    local_file = FileInfo(
        file_id=1234,
        parent_folder_id=0,
        name="Guitar.note",
        md5="77d180ea291127ee53b6a0b509e33f2a",  # MD5 of Guitar.note
        size=5,
        create_time=0,
        update_time=0,
    )
    local_path = store_path / "0" / "Guitar.note"
    local_path.parent.mkdir(parents=True)
    local_path.write_bytes(note_contents)

    result = await local_store.get_note_page_names(local_file)
    assert result == [
        "Guitar-000-P20231228174201877470DZj4cQ3c93Wi",
        "Guitar-001-P20240128210859017639qfzFJkp6gj2V",
    ]

    # We don't verify the actual page contents
    await local_store.get_note_png(local_file, 0)
