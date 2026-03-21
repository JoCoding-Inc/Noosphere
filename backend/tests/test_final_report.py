import pytest
from unittest.mock import AsyncMock, patch
from backend.reporter import generate_final_report
from backend.llm import LLMResponse

MOCK_ANALYSIS = "## Summary\nThis is a competitive market.\n## Existing Solutions\n- Competitor A\n"
MOCK_REPORT_JSON = {
    "verdict": "mixed",
    "evidence_count": 20,
    "segments": [
        {"name": "early_adopter", "sentiment": "positive", "summary": "Excited about the idea", "key_quotes": ["Love it!"]}
    ],
    "criticism_clusters": [
        {"theme": "Pricing concern", "count": 5, "examples": ["Too expensive"]}
    ],
    "improvements": [
        {"suggestion": "Add free tier", "frequency": 8}
    ],
}

@pytest.mark.asyncio
async def test_generate_final_report_returns_markdown():
    mock_response = LLMResponse(content="# Final Report\n\n## Executive Summary\nThis is promising.", tool_name=None, tool_args=None)
    with patch("backend.reporter.llm.complete", new_callable=AsyncMock, return_value=mock_response):
        result = await generate_final_report(
            analysis_md=MOCK_ANALYSIS,
            report_json=MOCK_REPORT_JSON,
            input_text="AI productivity tool",
            language="English",
            provider="openai",
        )
    assert isinstance(result, str)
    assert len(result) > 0


@pytest.mark.asyncio
async def test_generate_final_report_empty_inputs():
    """빈 데이터가 들어와도 fallback 문자열 반환"""
    result = await generate_final_report(
        analysis_md="",
        report_json={},
        input_text="",
        language="English",
        provider="openai",
    )
    assert isinstance(result, str)
    assert len(result) > 0


@pytest.mark.asyncio
async def test_generate_final_report_korean():
    mock_response = LLMResponse(content="# 최종 보고서\n\n## 종합 결론\n유망한 아이디어입니다.", tool_name=None, tool_args=None)
    with patch("backend.reporter.llm.complete", new_callable=AsyncMock, return_value=mock_response):
        result = await generate_final_report(
            analysis_md=MOCK_ANALYSIS,
            report_json=MOCK_REPORT_JSON,
            input_text="AI 생산성 도구",
            language="Korean",
            provider="openai",
        )
    assert "최종" in result or len(result) > 0
