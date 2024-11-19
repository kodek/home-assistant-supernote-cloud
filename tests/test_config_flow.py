"""Tests for the config flow."""

from unittest.mock import patch
from http import HTTPStatus
from freezegun import freeze_time

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.core import HomeAssistant
from homeassistant.const import (
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_ACCESS_TOKEN,
    CONF_UNIQUE_ID,
)

from custom_components.supernote_cloud.const import (
    DOMAIN,
    CONF_API_USERNAME,
    CONF_TOKEN_TIMESTAMP,
)

from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
)


@freeze_time("2021-01-01 12:00:00")
async def test_full_flow(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test selecting a device in the configuration flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result.get("type") is FlowResultType.FORM
    assert result.get("errors") is None

    aioclient_mock.post(
        "https://cloud.supernote.com/api/official/user/query/random/code",
        json={
            "randomCode": "abcdef",
            "timestamp": "17276692307051",
        },
    )
    aioclient_mock.post(
        "https://cloud.supernote.com/api/official/user/account/login/new",
        json={
            "success": True,
            "token": "access-token-1",
        },
    )
    aioclient_mock.post(
        "https://cloud.supernote.com/api/user/query",
        json={
            "success": True,
            "birthday": "2000-01-20T15:00:00.000Z",
            "countryCode": "1",
            "userName": "some-user-name",
            "userId": "654321",
        },
    )

    with patch(
        f"custom_components.{DOMAIN}.async_setup_entry", return_value=True
    ) as mock_setup:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "username",
                CONF_PASSWORD: "password",
            },
        )
        await hass.async_block_till_done()

    assert result.get("type") is FlowResultType.CREATE_ENTRY
    assert result.get("title") == "some-user-name"
    assert result.get("data") == {}
    assert result.get("options") == {
        CONF_USERNAME: "username",
        CONF_PASSWORD: "password",
        CONF_ACCESS_TOKEN: "access-token-1",
        CONF_UNIQUE_ID: "654321",
        CONF_API_USERNAME: "some-user-name",
        CONF_TOKEN_TIMESTAMP: 1609502400,
    }
    config_entry = result.get("result")
    assert config_entry
    assert config_entry.unique_id == "654321"

    assert len(mock_setup.mock_calls) == 1


async def test_get_code_failed(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test selecting a device in the configuration flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result.get("type") is FlowResultType.FORM
    assert result.get("errors") is None

    aioclient_mock.post(
        "https://cloud.supernote.com/api/official/user/query/random/code",
        status=HTTPStatus.BAD_REQUEST,
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: "username",
            CONF_PASSWORD: "password",
        },
    )
    await hass.async_block_till_done()
    assert result.get("type") is FlowResultType.FORM
    assert result.get("errors") == {"base": "api_error"}


async def test_user_query_failed(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test selecting a device in the configuration flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result.get("type") is FlowResultType.FORM
    assert result.get("errors") is None

    aioclient_mock.post(
        "https://cloud.supernote.com/api/official/user/query/random/code",
        json={
            "randomCode": "abcdef",
            "timestamp": "17276692307051",
        },
    )
    aioclient_mock.post(
        "https://cloud.supernote.com/api/official/user/account/login/new",
        json={
            "success": True,
            "token": "access-token-1",
        },
    )
    aioclient_mock.post(
        "https://cloud.supernote.com/api/user/query",
        status=HTTPStatus.BAD_REQUEST,
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: "username",
            CONF_PASSWORD: "password",
        },
    )
    await hass.async_block_till_done()
    assert result.get("type") is FlowResultType.FORM
    assert result.get("errors") == {"base": "api_error"}


@freeze_time("2021-01-01 12:00:00")
async def test_reauth_flow(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test reauth flow."""
    config_entry.async_start_reauth(hass)
    await hass.async_block_till_done()

    aioclient_mock.post(
        "https://cloud.supernote.com/api/official/user/query/random/code",
        json={
            "randomCode": "abcdef",
            "timestamp": "17276692307051",
        },
    )
    aioclient_mock.post(
        "https://cloud.supernote.com/api/official/user/account/login/new",
        json={
            "success": True,
            "token": "access-token-1",
        },
    )
    aioclient_mock.post(
        "https://cloud.supernote.com/api/user/query",
        json={
            "success": True,
            "birthday": "2000-01-20T15:00:00.000Z",
            "countryCode": "1",
            "userName": "some-user-name",
            "userId": "654321",
        },
    )

    # Advance through the reauth flow
    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    result = flows[0]
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {}
    )
    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "user"


    with patch(
        f"custom_components.{DOMAIN}.async_setup_entry", return_value=True
    ) as mock_setup:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "username",
                CONF_PASSWORD: "password",
            },
        )
        await hass.async_block_till_done()
    assert result.get("type") is FlowResultType.CREATE_ENTRY
    assert result.get("title") == "some-user-name"
    assert result.get("data") == {}
    assert result.get("options") == {
        CONF_USERNAME: "username",
        CONF_PASSWORD: "password",
        CONF_ACCESS_TOKEN: "access-token-1",
        CONF_UNIQUE_ID: "654321",
        CONF_API_USERNAME: "some-user-name",
        CONF_TOKEN_TIMESTAMP: 1609502400.0,
    }
    config_entry = result.get("result")
    assert config_entry
    assert config_entry.unique_id == "654321"

    assert len(mock_setup.mock_calls) == 1
