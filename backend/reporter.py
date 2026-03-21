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
        max_tokens=32768,
    )
    return response.content or ""


_FINAL_REPORT_SYSTEM = """\
You are a senior product analyst. You are given two inputs:
1. A competitive landscape analysis (from real-world sources)
2. A simulation report (from AI agent reactions to the idea)

Synthesize these into a final executive report with clear, actionable conclusions."""


def _fmt_report_json(report: dict) -> str:
    if not report:
        return "_No simulation data_"
    verdict = report.get("verdict", "unknown")
    evidence = report.get("evidence_count", 0)
    lines = [f"**Verdict:** {verdict} (based on {evidence} interactions)"]
    for seg in report.get("segments", []):
        lines.append(f"- Segment '{seg.get('name','')}': {seg.get('sentiment','')} — {seg.get('summary','')}")
    lines.append("\n**Top Criticisms:**")
    for c in report.get("criticism_clusters", [])[:3]:
        lines.append(f"- {c.get('theme','')} ({c.get('count',0)} mentions)")
    lines.append("\n**Top Improvements:**")
    for imp in report.get("improvements", [])[:3]:
        lines.append(f"- {imp.get('suggestion','')} (×{imp.get('frequency',1)})")
    return "\n".join(lines)


async def generate_final_report(
    analysis_md: str,
    report_json: dict,
    input_text: str,
    language: str = "English",
    provider: str = "openai",
) -> str:
    """
    analysis_md(소스 분석)와 report_json(시뮬레이션 결과)를 종합한
    최종 경영진 보고서를 생성합니다.
    """
    if not analysis_md and not report_json:
        return "## Final Report\n\n_No data available to generate final report._"

    sim_summary = _fmt_report_json(report_json)

    prompt = f"""Idea: {input_text[:400]}

---
## 1. Competitive Landscape Analysis
{analysis_md[:3000]}

---
## 2. Simulation Results Summary
{sim_summary}

---
Write the final report in this exact structure:
## Executive Summary
## Key Findings
## Risk Assessment
## Strategic Recommendations
## Conclusion

Be direct and actionable. Respond entirely in {language}."""

    response = await llm.complete(
        messages=[
            {"role": "system", "content": _FINAL_REPORT_SYSTEM},
            {"role": "user", "content": prompt},
        ],
        tier="high",
        provider=provider,
        max_tokens=8192,
    )
    return response.content or "## Final Report\n\n_Generation failed._"
