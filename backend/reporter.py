from __future__ import annotations
import logging
import os

import openai

logger = logging.getLogger(__name__)

_SYSTEM = """\
You are an expert at analysing competitive landscapes for technology ideas.
Given a list of real-world items gathered from GitHub, academic papers, HN, Reddit, Product Hunt, and other sources,
write a concise structured landscape report in markdown."""

_MODELS = ("gpt-5.4", "gpt-5.4-mini")

_client: openai.AsyncOpenAI | None = None


def _get_client() -> openai.AsyncOpenAI:
    global _client
    if _client is None:
        api_key = os.environ.get("OPENAI_API_KEY", "")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY not set")
        _client = openai.AsyncOpenAI(api_key=api_key, timeout=90.0)
    return _client


def _fmt_items(items: list[dict], limit: int = 10) -> str:
    lines = []
    for it in items[:limit]:
        title = it.get("title", "?")
        url = it.get("url", "")
        source = it.get("source", "")
        score = it.get("score", 0)
        text = (it.get("text") or "")[:120].replace("\n", " ")
        lines.append(f"- [{title}]({url}) (source={source}, score={score:.1f}) — {text}")
    return "\n".join(lines) if lines else "_없음_"


async def generate_analysis_report(
    raw_items: list[dict],
    domain: str,
    input_text: str,
    language: str = "English",
) -> str:
    """
    RawItem 리스트로 경쟁 환경 분석 보고서를 생성합니다.
    UMAP/KDE 없이 수집된 아이템만으로 Claude가 분석합니다.
    """
    if not raw_items:
        return "## Analysis Report\n\n수집된 데이터가 없습니다."

    # 소스별로 분류
    by_source: dict[str, list[dict]] = {}
    for item in raw_items:
        src = item.get("source", "unknown")
        by_source.setdefault(src, []).append(item)

    # 점수 기준 상위 아이템
    top_items = sorted(raw_items, key=lambda x: -float(x.get("score", 0)))

    source_summary = "\n".join(
        f"- {src}: {len(items)}개" for src, items in sorted(by_source.items())
    )

    prompt = f"""Domain: {domain}
Idea: {input_text[:400]}

Collected {len(raw_items)} items from: {', '.join(sorted(by_source.keys()))}

Source breakdown:
{source_summary}

Top items by relevance/score:
{_fmt_items(top_items, limit=15)}

Write a landscape report in this exact structure:
## Summary
## Existing Solutions (Top 5 most relevant)
## Market Gaps / Blue Ocean Opportunities
## Key Players & Communities
## Recommended Positioning

Respond entirely in {language}."""

    client = _get_client()
    for model in _MODELS:
        try:
            response = await client.chat.completions.create(
                model=model,
                max_tokens=8192,
                messages=[
                    {"role": "system", "content": _SYSTEM},
                    {"role": "user", "content": prompt},
                ],
            )
            content = response.choices[0].message.content
            if content:
                return content
        except Exception as exc:
            logger.warning("Reporter model %s failed: %s", model, exc)

    return "## Analysis Report\n\nReport generation failed."
