import pytest
from unittest.mock import AsyncMock, patch
from backend.llm import LLMResponse
from backend.simulation.models import Persona


async def test_generate_persona_returns_persona():
    tool_args = {
        "name": "Alice Chen", "role": "Software Engineer", "age": 28,
        "generation": "Millennial", "seniority": "mid", "affiliation": "employee",
        "company": "TechCorp", "mbti": "INTJ", "bias": "tech_optimist",
        "interests": ["AI", "SaaS"], "skepticism": 3, "commercial_focus": 5,
        "innovation_openness": 8,
    }
    mock_response = LLMResponse(content=None, tool_name="create_persona", tool_args=tool_args)
    with patch("backend.simulation.persona_generator.llm") as mock_llm:
        mock_llm.complete = AsyncMock(return_value=mock_response)
        from backend.simulation.persona_generator import generate_persona
        node = {"id": "node1", "title": "AI SaaS", "source": "arxiv", "abstract": "..."}
        persona = await generate_persona(node, idea_text="AI SaaS", platform_name="hackernews", provider="openai")
    assert isinstance(persona, Persona)
    assert persona.name == "Alice Chen"


@pytest.mark.asyncio
async def test_generate_persona_with_ontology_injects_context():
    """Ontology context should appear in the prompt sent to LLM."""
    from unittest.mock import AsyncMock, patch
    from backend.llm import LLMResponse

    tool_args = {
        "name": "Alice Chen", "role": "Engineer", "age": 28,
        "seniority": "mid", "affiliation": "individual",
        "company": "TechCorp", "mbti": "INTJ",
        "interests": ["AI"], "skepticism": 3,
        "commercial_focus": 5, "innovation_openness": 8,
    }
    fake_ontology = {
        "domain_summary": "RAG tooling ecosystem",
        "entities": [{"id": "e0", "name": "LangChain", "type": "framework", "source_node_ids": []}],
        "relationships": [],
        "market_tensions": ["build vs buy"],
        "key_trends": [],
    }
    mock_response = LLMResponse(content=None, tool_name="create_persona", tool_args=tool_args)

    captured_messages = []
    async def mock_complete(**kwargs):
        captured_messages.extend(kwargs.get("messages", []))
        return mock_response

    with patch("backend.simulation.persona_generator.llm") as mock_llm:
        mock_llm.complete = mock_complete
        from backend.simulation.persona_generator import generate_persona
        node = {"id": "node1", "title": "AI SaaS", "source": "arxiv", "abstract": "..."}
        await generate_persona(node, idea_text="RAG app", platform_name="hackernews",
                               provider="openai", ontology=fake_ontology)

    all_text = " ".join(m["content"] for m in captured_messages)
    assert "RAG tooling ecosystem" in all_text
