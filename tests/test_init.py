"""Tests for the supernote_cloud component."""

import pytest

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntryState

from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
)



@pytest.fixture(autouse=True)
def mock_setup_integration(config_entry: MockConfigEntry) -> None:
    """Setup the integration"""


@pytest.mark.usefixtures("setup_integration")
async def test_init(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Setup the integration"""

    assert config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert (
        config_entry.state is ConfigEntryState.NOT_LOADED  # type: ignore[comparison-overlap]
    )
