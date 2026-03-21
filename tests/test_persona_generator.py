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
