"""Fixtures for the custom component."""

from collections.abc import Generator, AsyncGenerator
import logging
from unittest.mock import patch

import pytest

from homeassistant.const import (
    Platform,
    CONF_ACCESS_TOKEN,
    CONF_UNIQUE_ID,
    CONF_PASSWORD,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
)

from custom_components.supernote_cloud.const import (
    DOMAIN,
    CONF_TOKEN_TIMESTAMP,
    CONF_API_USERNAME,
)

_LOGGER = logging.getLogger(__name__)


CONFIG_ENTRY_ID = "user-identifier-1"
CONFIG_ENTRY_TITLE = "user-name"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(
    enable_custom_integrations: None,
) -> Generator[None, None, None]:
    """Enable custom integration."""
    _ = enable_custom_integrations  # unused
    yield


@pytest.fixture(name="platforms")
def mock_platforms() -> list[Platform]:
    """Fixture for platforms loaded by the integration."""
    return []


@pytest.fixture(name="setup_integration")
async def mock_setup_integration(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    platforms: list[Platform],
) -> AsyncGenerator[None]:
    """Set up the integration."""

    with patch(f"custom_components.{DOMAIN}.PLATFORMS", platforms):
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()
        yield


@pytest.fixture(name="config_entry")
async def mock_config_entry(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> MockConfigEntry:
    """Fixture to create a configuration entry."""
    config_entry = MockConfigEntry(
        unique_id=CONFIG_ENTRY_ID,
        title=CONFIG_ENTRY_TITLE,
        domain=DOMAIN,
        options={
            CONF_ACCESS_TOKEN: "access-token-1",
            CONF_TOKEN_TIMESTAMP: dt_util.now().timestamp(),
            CONF_UNIQUE_ID: CONFIG_ENTRY_ID,
            CONF_API_USERNAME: "user-name",
            CONF_PASSWORD: "some-password",
        },
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    return config_entry
