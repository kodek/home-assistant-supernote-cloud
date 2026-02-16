"""Test the Supernote Cloud LLM tools."""

from unittest.mock import AsyncMock

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers import llm

from custom_components.supernote_cloud.llm import (
    SearchTool,
    TranscriptTool,
)

from supernote.models.extended import (
    WebSearchResponseVO,
    SearchResultVO,
    WebTranscriptResponseVO,
)

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


@pytest.mark.usefixtures("mock_supernote")
async def test_transcript_tool_initialization(
    hass: HomeAssistant, config_entry: MockConfigEntry
):
    """Test initializing the transcript tool."""
    tool = TranscriptTool(config_entry)
    assert tool.name == "get_supernote_transcript"
    assert (
        tool.description
        == "Retrieve the text transcript for a Supernote notebook by file ID."
    )


@pytest.mark.usefixtures("mock_supernote")
async def test_search_tool_call_success(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_supernote: AsyncMock,
):
    """Test calling the search tool successfully."""
    # Ensure runtime_data is mock_supernote
    config_entry.runtime_data = mock_supernote

    # Setup mock response
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

    # Configure post_json to return the response
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

    # Verify post_json call
    mock_supernote.client.post_json.assert_called_once()
    args, kwargs = mock_supernote.client.post_json.call_args
    assert args[0] == "/api/extended/search"
    assert kwargs["json"]["query"] == "test query"
    assert kwargs["json"]["topN"] == 3


@pytest.mark.usefixtures("mock_supernote")
async def test_transcript_tool_call_success(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_supernote: AsyncMock,
):
    """Test calling the transcript tool successfully."""
    # Ensure runtime_data is mock_supernote
    config_entry.runtime_data = mock_supernote

    # Setup mock response
    mock_response = WebTranscriptResponseVO(transcript="This is the full transcript.")

    # Configure post_json to return the response
    mock_supernote.client.post_json = AsyncMock(return_value=mock_response)

    tool = TranscriptTool(config_entry)

    tool_input = llm.ToolInput(
        tool_name="get_supernote_transcript", tool_args={"file_id": 12345}
    )

    result = await tool.async_call(hass, tool_input, AsyncMock())

    assert result == {
        "transcript": "This is the full transcript.",
    }

    # Verify post_json call
    mock_supernote.client.post_json.assert_called_once()
    args, kwargs = mock_supernote.client.post_json.call_args
    assert args[0] == "/api/extended/transcript"
    assert kwargs["json"]["fileId"] == 12345


@pytest.mark.usefixtures("mock_supernote")
async def test_search_tool_call_error(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_supernote: AsyncMock,
):
    """Test calling the search tool with an error."""
    # Ensure runtime_data is mock_supernote
    config_entry.runtime_data = mock_supernote

    mock_supernote.client.post_json = AsyncMock(side_effect=Exception("API Error"))

    tool = SearchTool(config_entry)

    tool_input = llm.ToolInput(
        tool_name="search_supernote", tool_args={"query": "test query"}
    )

    result = await tool.async_call(hass, tool_input, AsyncMock())

    assert result == {"error": "Error searching Supernote: API Error"}


@pytest.mark.usefixtures("mock_supernote")
async def test_transcript_tool_call_error(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_supernote: AsyncMock,
):
    """Test calling the transcript tool with an error."""
    # Ensure runtime_data is mock_supernote
    config_entry.runtime_data = mock_supernote

    mock_supernote.client.post_json = AsyncMock(side_effect=Exception("API Error"))

    tool = TranscriptTool(config_entry)

    tool_input = llm.ToolInput(
        tool_name="get_supernote_transcript", tool_args={"file_id": 12345}
    )

    result = await tool.async_call(hass, tool_input, AsyncMock())

    assert result == {"error": "Error fetching Supernote transcript: API Error"}
