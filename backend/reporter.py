from __future__ import annotations
import logging
from typing import Any

from backend import llm

logger = logging.getLogger(__name__)

_SYSTEM = """\
You are an expert at analysing competitive landscapes for technology ideas.
Given a list of real-world items gathered from GitHub, academic papers, HN, Reddit, Product Hunt, and other sources,
write a concise structured landscape report in markdown."""


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
    provider: str = "openai",
) -> str:
    """
    RawItem 리스트로 경쟁 환경 분석 보고서를 생성합니다.
    """
    if not raw_items:
        return "## Analysis Report\n\n수집된 데이터가 없습니다."

    by_source: dict[str, list[dict]] = {}
    for item in raw_items:
        src = item.get("source", "unknown")
        by_source.setdefault(src, []).append(item)

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

    response = await llm.complete(
        messages=[
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": prompt},
        ],
        tier="high",
        provider=provider,
        max_tokens=8192,
    )
    return response.content or ""
