from __future__ import annotations
import logging
import math

from backend import llm

logger = logging.getLogger(__name__)

_SYSTEM = """\
You are an expert at analysing competitive landscapes for technology ideas.
Given a list of real-world items gathered from GitHub, academic papers, HN, Reddit, Product Hunt, and other sources,
write a concise structured landscape report in markdown."""


def _coerce_score(value: object) -> float:
    """Normalize score-like values for display and sorting."""
    try:
        score = float(value or 0)
    except (TypeError, ValueError):
        return 0.0
    return score if math.isfinite(score) else 0.0


def _fmt_items(items: list[dict], limit: int = 10) -> str:
    lines = []
    for it in items[:limit]:
        title = it.get("title", "?")
        url = it.get("url", "")
        source = it.get("source", "")
        score = _coerce_score(it.get("score"))
        text = (it.get("text") or "")[:120].replace("\n", " ")
        lines.append(f"- [{title}]({url}) (source={source}, score={score:.1f}) — {text}")
    return "\n".join(lines) if lines else "_없음_"


async def generate_analysis_report(
    raw_items: list[dict],
    domain: str,
    input_text: str,
    language: str = "English",
    idea_title: str = "",
    top_competitors: list[dict] | None = None,
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

    # Round-robin: ensure at least 1 item per source, then fill by score
    _limit = 15
    _seen_ids: set[int] = set()
    top_items: list[dict] = []
    # Phase 1: pick best item from each source (round-robin)
    for _src in sorted(by_source.keys()):
        _src_items = sorted(by_source[_src], key=lambda x: -_coerce_score(x.get("score")))
        if _src_items:
            top_items.append(_src_items[0])
            _seen_ids.add(id(_src_items[0]))
    # Phase 2: fill remaining slots by global score
    if len(top_items) < _limit:
        _remaining = sorted(raw_items, key=lambda x: -_coerce_score(x.get("score")))
        for _it in _remaining:
            if id(_it) not in _seen_ids:
                top_items.append(_it)
                _seen_ids.add(id(_it))
                if len(top_items) >= _limit:
                    break

    source_summary = "\n".join(
        f"- {src}: {len(items)}개" for src, items in sorted(by_source.items())
    )

    idea_line = f"{idea_title}: {input_text}" if idea_title else input_text

    # Build top competitors section
    competitors_section = ""
    if top_competitors:
        comp_lines = []
        for comp in top_competitors[:3]:
            c_title = comp.get("title", "?")
            c_url = comp.get("url", "")
            c_source = comp.get("source", "")
            c_abstract = (comp.get("abstract") or "")[:150]
            comp_lines.append(f"- [{c_title}]({c_url}) (source={c_source}) — {c_abstract}")
        competitors_section = "\nTop 3 closest competitors:\n" + "\n".join(comp_lines) + "\n"

    prompt = f"""Domain: {domain}
Idea: {idea_line}

Collected {len(raw_items)} items from: {', '.join(sorted(by_source.keys()))}

Source breakdown:
{source_summary}

Top items by relevance/score:
{_fmt_items(top_items, limit=15)}
{competitors_section}
Write a landscape report in this exact structure:
## Summary
## Existing Solutions (Top 5 most relevant)
{"## Top 3 Closest Competitors" if top_competitors else ""}
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
        max_tokens=32768,
    )
    return response.content or ""


_GTM_SYSTEM = """\
You are a go-to-market strategist specializing in early-stage product launches.
Given simulation results showing how different communities reacted to a product idea,
generate a concrete, actionable launch strategy.
Focus on: where to launch, who to target first, how to message, and what risks to pre-empt."""


def _fmt_top_posts(top_posts: list[dict]) -> str:
    """Format top agent posts for inclusion in GTM prompt."""
    lines = ["\nReal agent quotes from simulation (use these for concrete messaging examples):"]
    for post in top_posts[:12]:
        platform = post.get("platform", "")
        author = post.get("author_name", "")
        content = post.get("content", "")[:200]
        sentiment = post.get("sentiment", "neutral")
        upvotes = post.get("upvotes", 0)
        lines.append(f'- [{platform}/{sentiment}] {author}: "{content}" (upvotes: {upvotes})')
    return "\n".join(lines)


async def generate_gtm_report(
    report_json: dict,
    analysis_md: str,
    input_text: str,
    language: str = "English",
    platform_summaries: dict | None = None,
    top_posts: list[dict] | None = None,
    interaction_summary: str = "",
    conversion_funnel: dict | None = None,
    unaddressed_concerns: list | None = None,
    debate_highlights: str = "",
) -> str:
    """
    시뮬레이션 결과(report_json)와 경쟁 분석(analysis_md)을 기반으로
    Go-to-Market 전략 보고서를 생성합니다.
    """
    if not report_json:
        return "## Launch Strategy\n\n_No simulation data available._"

    verdict = report_json.get("verdict", "mixed")
    segments = report_json.get("segments", [])
    criticisms = report_json.get("criticism_clusters", [])
    improvements = report_json.get("improvements", [])
    praise_clusters = report_json.get("praise_clusters", [])

    # Build segment sentiment summary with detailed data
    seg_lines = []
    for seg in segments:
        name = seg.get('name', '')
        sentiment = seg.get('sentiment', 'neutral')
        summary = seg.get('summary', '')[:150]
        # Include sentiment ratio and sample quote if available
        key_quotes = seg.get('key_quotes', [])
        sample_quote = key_quotes[0][:120] if key_quotes else ""
        sentiment_ratio = seg.get('sentiment_ratio', '')
        ratio_str = f" (ratio: {sentiment_ratio})" if sentiment_ratio else ""
        quote_str = f' | sample: "{sample_quote}"' if sample_quote else ""
        seg_lines.append(f"- {name}: {sentiment}{ratio_str} — {summary}{quote_str}")
    seg_summary = "\n".join(seg_lines) if seg_lines else "No segment data"

    # Build criticism summary
    crit_lines = []
    for c in criticisms:
        crit_lines.append(f"- {c.get('theme', '')} ({c.get('count', 0)} mentions)")
    crit_summary = "\n".join(crit_lines) if crit_lines else "No criticisms recorded"

    # Build improvements summary
    imp_lines = []
    for imp in improvements:
        imp_lines.append(f"- {imp.get('suggestion', '')} (×{imp.get('frequency', 1)})")
    imp_summary = "\n".join(imp_lines) if imp_lines else "No improvements recorded"

    # Build praise/strengths summary
    praise_lines = []
    for p in praise_clusters:
        praise_lines.append(f"- {p.get('theme', '')} ({p.get('count', 0)} mentions)")
    praise_summary = "\n".join(praise_lines) if praise_lines else ""

    # Build platform reception section if available
    platform_reception = ""
    if platform_summaries:
        reception_lines = []
        for plat, stats in platform_summaries.items():
            if isinstance(stats, dict):
                positive_pct = stats.get("positive_pct", stats.get("positive", 0))
                total = stats.get("total", stats.get("count", 0))
                reception_lines.append(f"{plat} {positive_pct}% positive ({total} total)")
        if reception_lines:
            platform_reception = f"\nPlatform reception: {', '.join(reception_lines)}\n"

    # Extract peak positive round per platform from timeline
    peak_lines = ""
    pst = report_json.get("platform_sentiment_timeline")
    if pst and isinstance(pst, dict):
        peak_rounds: dict[str, dict] = {}
        for pname, rounds_list in pst.items():
            if not isinstance(rounds_list, list):
                continue
            for entry in rounds_list:
                rn = entry.get("round")
                pos = entry.get("positive", 0)
                total = pos + entry.get("neutral", 0) + entry.get("negative", 0) + entry.get("constructive", 0)
                total = total or 1
                pos_pct = pos / total
                if pname not in peak_rounds or pos_pct > peak_rounds[pname]["pct"]:
                    peak_rounds[pname] = {"round": rn, "pct": round(pos_pct * 100)}
        if peak_rounds:
            peak_lines = "\n".join(
                f"- {pname}: peaked at round {v['round']} ({v['pct']}% positive)"
                for pname, v in peak_rounds.items()
            )

    peak_section = ""
    if peak_lines:
        peak_section = f"""
Platform engagement timing:
{peak_lines}
Use this timing data to recommend when and in what order to launch on each platform.
"""

    # Build segment-platform cross-analysis matrix
    platform_segments = report_json.get("platform_segments", {})
    matrix_lines = []
    for platform_name, segs in platform_segments.items():
        if not segs:
            continue
        # effective_positive_pct 기준 상위 3개 세그먼트 (constructive를 절반 가산한 실질 positive 비율)
        sorted_segs = sorted(
            [(seg, data) for seg, data in segs.items() if isinstance(data, dict)],
            key=lambda x: x[1].get("effective_positive_pct", x[1].get("positive_pct", 0)),
            reverse=True
        )[:3]
        if sorted_segs:
            parts = [f"{seg}({data.get('effective_positive_pct', data.get('positive_pct', 0))}% eff-pos)" for seg, data in sorted_segs]
            matrix_lines.append(f"- {platform_name}: {', '.join(parts)}")

    if matrix_lines:
        segment_matrix_section = "\nSegment-Platform Matrix (top 3 positive segments per platform):\n" + "\n".join(matrix_lines) + "\n"
    else:
        segment_matrix_section = ""

    interaction_section = ""
    if interaction_summary:
        interaction_section = (
            f"\n## Segment Interaction Patterns\n{interaction_summary}\n"
            f"Use these patterns to identify which segments influence others and recommend influencer-first targeting strategies.\n"
        )

    # Build conversion funnel section
    funnel_section = ""
    if conversion_funnel and isinstance(conversion_funnel, dict):
        funnel_lines = []
        for seg_name, seg_data in list(conversion_funnel.items())[:5]:
            if isinstance(seg_data, dict):
                conv = seg_data.get("conversion_rate", 0)
                res = seg_data.get("resistance_rate", 0)
                funnel_lines.append(f"- {seg_name}: {conv:.1f}%\u2192positive, {res:.1f}%\u2192negative")
        if funnel_lines:
            funnel_section = (
                "\n### Segment Conversion Funnel\n"
                + "\n".join(funnel_lines)
                + "\n"
            )

    # Build unaddressed concerns section
    concerns_section = ""
    if unaddressed_concerns and isinstance(unaddressed_concerns, list):
        concern_lines = []
        for c in unaddressed_concerns[:5]:
            if isinstance(c, dict):
                plat = c.get("platform", "?")
                seg = c.get("author_segment", "?")
                sent = c.get("sentiment", "?")
                snippet = (c.get("content_snippet") or c.get("snippet") or c.get("content", ""))[:120]
                concern_lines.append(f"- {plat} | {seg} | {sent} | {snippet}")
        if concern_lines:
            concerns_section = (
                "\n### Unaddressed Market Concerns\n"
                + "\n".join(concern_lines)
                + "\n"
            )

    debate_highlights_section = ""
    if debate_highlights:
        debate_highlights_section = f"\n### Debate Turning Points\n{debate_highlights}\n"

    prompt = f"""Product idea: {input_text}
{platform_reception}{peak_section}{segment_matrix_section}{interaction_section}{funnel_section}{concerns_section}{debate_highlights_section}
Overall verdict: {verdict}

Segment reactions:
{seg_summary}

Top criticisms:
{crit_summary}

Top improvement suggestions:
{imp_summary}
{"" if not praise_summary else f"""
Strengths / What resonated:
{praise_summary}
"""}Competitive context (summary):
{analysis_md[:1500]}
{"" if not top_posts else _fmt_top_posts(top_posts)}

---
Generate a Go-to-Market strategy report with this EXACT structure:

## Platform Priority
Rank the 5 platforms (Hacker News, Product Hunt, Indie Hackers, Reddit r/startups, LinkedIn) by launch priority based on which segments responded most positively. For each, explain WHY and HOW to approach it specifically.

## Ideal Customer Profile (ICP)
Based on the segments with positive/neutral sentiment, define the primary ICP: who they are, what job they're trying to do, what triggers them to seek a solution.

## Messaging Strategy
For each segment, specify: tone (e.g. authoritative, empathetic, technical), key angle (the primary hook for this audience), and what to emphasize/avoid in messaging. Then, for each top criticism cluster, write a specific counter-message or positioning adjustment. How should the product be framed to pre-empt the objection? Also, leverage the positive themes from "Strengths / What resonated" to craft positioning that amplifies what already works.

## Product Priorities Before Launch
From the improvement suggestions, identify the top 2-3 things to fix or add BEFORE the first public launch to maximize reception.

## Pricing & Monetization Strategy
Based on the segment reactions (especially commercial-focus personas' feedback), recommend: initial pricing model (freemium/paid/usage-based), target price point range, and freemium vs. paid-only rationale. Pay close attention to investor and product manager segments' sentiment toward monetization signals, and any criticism or praise related to pricing, value perception, or willingness to pay.

## Risk Assessment
Apply inversion thinking: what are the 2-3 most likely ways this launch could fail, and what would prevent each?

Respond entirely in {language}. Be specific and actionable, not generic."""

    response = await llm.complete(
        messages=[
            {"role": "system", "content": _GTM_SYSTEM},
            {"role": "user", "content": prompt},
        ],
        tier="high",
        max_tokens=8192,
        timeout=300.0,
    )
    return response.content or "## Launch Strategy\n\n_Generation failed._"


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
    gtm_md: str = "",
    agent_count: int = 0,
    round_count: int = 0,
    sentiment_distribution: dict | None = None,
) -> str:
    """
    analysis_md(소스 분석)와 report_json(시뮬레이션 결과)를 종합한
    최종 경영진 보고서를 생성합니다.
    """
    if not analysis_md and not report_json:
        return "## Final Report\n\n_No data available to generate final report._"

    sim_summary = _fmt_report_json(report_json)

    gtm_section = ""
    if gtm_md:
        gtm_section = f"""
---
## 3. Go-to-Market Strategy
{gtm_md[:3000]}
"""

    # Build simulation metadata section
    sim_meta_lines = []
    if agent_count:
        sim_meta_lines.append(f"- Agents: {agent_count}")
    if round_count:
        sim_meta_lines.append(f"- Rounds: {round_count}")
    if sentiment_distribution:
        dist_parts = [f"{k}: {v}" for k, v in sentiment_distribution.items()]
        sim_meta_lines.append(f"- Sentiment distribution: {', '.join(dist_parts)}")
    sim_meta = "\n".join(sim_meta_lines) if sim_meta_lines else ""
    sim_meta_section = f"\n\nSimulation parameters:\n{sim_meta}" if sim_meta else ""

    # Build key metrics block from report_json
    key_metrics_lines = []
    adoption_score = report_json.get("adoption_score")
    if adoption_score is not None:
        key_metrics_lines.append(f"- Adoption score: {adoption_score}/10")

    platform_summaries = report_json.get("platform_summaries")
    if platform_summaries and isinstance(platform_summaries, dict):
        best_platform = None
        best_pct = -1
        for plat_name, plat_stats in platform_summaries.items():
            if isinstance(plat_stats, dict):
                pct = plat_stats.get("positive_pct", plat_stats.get("positive", 0))
                if isinstance(pct, (int, float)) and pct > best_pct:
                    best_pct = pct
                    best_platform = plat_name
        if best_platform is not None:
            key_metrics_lines.append(f"- Most positive platform: {best_platform} ({best_pct}% positive)")

    key_debates = report_json.get("key_debates")
    if key_debates and isinstance(key_debates, list):
        debate_titles = [d.get("title", d) if isinstance(d, dict) else str(d) for d in key_debates[:5]]
        key_metrics_lines.append(f"- Key debates: {', '.join(debate_titles)}")

    segments = report_json.get("segments")
    if segments and isinstance(segments, list):
        seg_counts: dict[str, int] = {}
        for seg in segments:
            seg_name = seg.get("name", "")
            if seg_name:
                seg_counts[seg_name] = seg_counts.get(seg_name, 0) + 1
        if seg_counts:
            primary_segment = max(seg_counts, key=seg_counts.get)
            key_metrics_lines.append(f"- Primary segment: {primary_segment}")

    key_metrics_block = ""
    if key_metrics_lines:
        key_metrics_block = "\nKey metrics:\n" + "\n".join(key_metrics_lines) + "\n"

    prompt = f"""Idea: {input_text}

---
## 1. Competitive Landscape Analysis
{analysis_md[:3000]}

---
## 2. Simulation Results Summary
{sim_summary}{sim_meta_section}
{gtm_section}{key_metrics_block}
---
Write the final report in this exact structure:
## Executive Summary
## Key Findings
## Risk Assessment
## Strategic Recommendations
## Simulation Confidence
Rate the simulation confidence as: High / Medium / Low with 1-2 sentence rationale. Consider the following criteria: Higher confidence comes from 100+ agents, 8+ rounds, balanced sentiment distribution, and cross-platform consistency. Lower confidence comes from fewer agents, fewer rounds, heavily skewed sentiment, or single-platform data.
## Conclusion

Be direct and actionable. Synthesize all available inputs. Respond entirely in {language}."""

    response = await llm.complete(
        messages=[
            {"role": "system", "content": _FINAL_REPORT_SYSTEM},
            {"role": "user", "content": prompt},
        ],
        tier="high",
        max_tokens=8192,
        timeout=300.0,
    )
    return response.content or "## Final Report\n\n_Generation failed._"
