import pytest
from unittest.mock import AsyncMock, patch
from backend.llm import LLMResponse


async def test_extract_concepts_returns_list():
    mock_response = LLMResponse(content='["task management", "SaaS", "productivity"]', tool_name=None, tool_args=None)
    with patch("backend.context_builder.llm") as mock_llm:
        mock_llm.complete = AsyncMock(return_value=mock_response)
        from backend.context_builder import extract_concepts_from_text
        result = await extract_concepts_from_text("A SaaS app for task management", provider="openai")
    assert isinstance(result, list)
    assert len(result) > 0


async def test_build_context_nodes_from_text_only():
    mock_response = LLMResponse(content='["task management", "productivity"]', tool_name=None, tool_args=None)
    with patch("backend.context_builder.llm") as mock_llm:
        mock_llm.complete = AsyncMock(return_value=mock_response)
        from backend.context_builder import build_context_nodes
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
