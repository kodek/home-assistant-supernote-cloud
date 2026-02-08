"""Supernote Cloud types."""

from homeassistant.config_entries import ConfigEntry
from supernote.client.api import Supernote

type SupernoteCloudConfigEntry = ConfigEntry[Supernote]
