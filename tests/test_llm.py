"""Test the Supernote Cloud LLM tools."""

from unittest.mock import AsyncMock

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import llm

from custom_components.supernote_cloud.llm import SearchTool

from supernote.models.extended import WebSearchResponseVO, SearchResultVO

from pytest_homeassistant_custom_component.common import MockConfigEntry


@pytest.mark.usefixtures("mock_supernote")
async def test_search_tool_initialization(
    hass: HomeAssistant, config_entry: MockConfigEntry
):
    """Test initializing the search tool."""
    tool = SearchTool(config_entry)
    assert tool.name == "search_supernote"
    assert (
        tool.description
        == "Search for content in Supernote notebooks using semantic search."
    )


@pytest.mark.usefixtures("setup_integration")
async def test_search_tool_call_success(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_supernote: AsyncMock,
):
    """Test calling the search tool successfully."""
    mock_result = SearchResultVO(
        file_id=123,
        file_name="Test Note",
        page_index=1,
        page_id="page_1",
        score=0.95,
        text_preview="This is a test note content.",
        date="2023-10-27",
    )
    mock_response = WebSearchResponseVO(results=[mock_result])

    mock_supernote.client.post_json = AsyncMock(return_value=mock_response)

    tool = SearchTool(config_entry)

    tool_input = llm.ToolInput(
        tool_name="search_supernote", tool_args={"query": "test query", "top_n": 3}
    )

    result = await tool.async_call(hass, tool_input, AsyncMock())

    assert result == {
        "results": [
            {
                "file_name": "Test Note",
                "page_index": 1,
                "text_preview": "This is a test note content.",
                "score": 0.95,
                "date": "2023-10-27",
            }
        ]
    }

    mock_supernote.client.post_json.assert_called_once()
    args, kwargs = mock_supernote.client.post_json.call_args
    assert args[0] == "/api/extended/search"
    assert kwargs["json"]["query"] == "test query"
    assert kwargs["json"]["topN"] == 3


@pytest.mark.usefixtures("setup_integration")
async def test_search_tool_call_error(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_supernote: AsyncMock,
):
    """Test calling the search tool with an error."""
    mock_supernote.client.post_json = AsyncMock(side_effect=Exception("API Error"))

    tool = SearchTool(config_entry)

    tool_input = llm.ToolInput(
        tool_name="search_supernote", tool_args={"query": "test query"}
    )

    with pytest.raises(HomeAssistantError, match="Error searching Supernote"):
        await tool.async_call(hass, tool_input, AsyncMock())
