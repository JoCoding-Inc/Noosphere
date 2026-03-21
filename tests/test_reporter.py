from unittest.mock import AsyncMock, patch
from backend.llm import LLMResponse


async def test_generate_analysis_report_with_provider():
    mock_response = LLMResponse(content="## Summary\n\nTest report.", tool_name=None, tool_args=None)
    with patch("backend.reporter.llm") as mock_llm:
        mock_llm.complete = AsyncMock(return_value=mock_response)
        from backend.reporter import generate_analysis_report
        result = await generate_analysis_report(
            raw_items=[{"title": "Item", "source": "github", "score": 1.0}],
            domain="tech",
            input_text="A SaaS app",
            language="English",
            provider="openai",
        )
    assert isinstance(result, str)
    assert len(result) > 0


async def test_generate_analysis_report_empty_items():
    from backend.reporter import generate_analysis_report
    result = await generate_analysis_report(
        raw_items=[],
        domain="tech",
        input_text="A SaaS app",
        language="English",
        provider="openai",
    )
    assert "Analysis Report" in result
