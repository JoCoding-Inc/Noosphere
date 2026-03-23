from backend import reporter


def test_fmt_items_tolerates_invalid_scores():
    output = reporter._fmt_items([
        {
            "title": "Broken",
            "url": "https://example.com/broken",
            "source": "reddit",
            "score": "N/A",
            "text": "alpha",
        },
        {
            "title": "Infinite",
            "url": "https://example.com/infinite",
            "source": "hn",
            "score": "inf",
            "text": "beta",
        },
    ])

    assert "score=0.0" in output


def test_coerce_score_rejects_non_finite_values():
    assert reporter._coerce_score("nan") == 0.0
    assert reporter._coerce_score("inf") == 0.0
    assert reporter._coerce_score("-inf") == 0.0


def test_generate_analysis_report_sorts_with_safe_scores(monkeypatch):
    captured: dict[str, object] = {}

    async def fake_complete(**kwargs):
        captured["messages"] = kwargs["messages"]
        return reporter.llm.LLMResponse(content="ok", tool_name=None, tool_args=None)

    monkeypatch.setattr(reporter.llm, "complete", fake_complete)

    result = reporter.generate_analysis_report(
        raw_items=[
            {"title": "Bad", "url": "https://example.com/bad", "source": "reddit", "score": "N/A", "text": "bad"},
            {"title": "Good", "url": "https://example.com/good", "source": "github", "score": "3.5", "text": "good"},
            {"title": "Weird", "url": "https://example.com/weird", "source": "hn", "score": "nan", "text": "weird"},
        ],
        domain="AI",
        input_text="Idea",
    )

    import asyncio

    assert asyncio.run(result) == "ok"
    prompt = captured["messages"][1]["content"]
    assert prompt.index("[Good]") < prompt.index("[Bad]")
