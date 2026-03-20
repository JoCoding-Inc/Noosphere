import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from backend.context_builder import extract_concepts_from_text, build_context_nodes


@pytest.mark.asyncio
async def test_extract_concepts_returns_list():
    """extract_concepts_from_text returns list of concept dicts."""
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text='["task management", "SaaS", "productivity"]')]

    with patch("backend.context_builder._get_client") as mock_get_client:
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)
        mock_get_client.return_value = mock_client

        result = await extract_concepts_from_text("A SaaS app for task management")
        assert isinstance(result, list)
        assert len(result) > 0


@pytest.mark.asyncio
async def test_build_context_nodes_from_text_only():
    """build_context_nodes returns valid node dicts even without external fetch."""
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text='["task management", "productivity"]')]

    with patch("backend.context_builder._get_client") as mock_get_client:
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)
        mock_get_client.return_value = mock_client

        nodes = await build_context_nodes(
            "A SaaS app for task management",
            enrich=False,
        )
        assert len(nodes) >= 1
        for node in nodes:
            assert "id" in node
            assert "title" in node
            assert "source" in node
            assert "abstract" in node
            assert node["source"] == "input_text"
