"""Supernote Cloud types."""

from homeassistant.config_entries import ConfigEntry
from .store.store import LocalStore

type SupernoteCloudConfigEntry = ConfigEntry[LocalStore]  # type: ignore[valid-type]
