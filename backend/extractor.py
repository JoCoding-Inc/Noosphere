from __future__ import annotations
import json
import logging
import os
import re
from typing import Any

import anthropic

logger = logging.getLogger(__name__)

_client: anthropic.AsyncAnthropic | None = None

DOMAIN_QUERY_COUNTS = {
    "tech":       {"code": 5, "academic": 5, "discussion": 3, "product": 2, "news": 1},
    "research":   {"code": 2, "academic": 6, "discussion": 2, "product": 0, "news": 2},
    "consumer":   {"code": 1, "academic": 0, "discussion": 3, "product": 5, "news": 2},
    "business":   {"code": 2, "academic": 0, "discussion": 2, "product": 4, "news": 3},
    "healthcare": {"code": 2, "academic": 5, "discussion": 2, "product": 1, "news": 3},
    "general":    {"code": 2, "academic": 2, "discussion": 3, "product": 2, "news": 3},
}

_SYSTEM = """\
You are a search query strategist. Given a product/idea description, extract concepts and generate targeted search queries for different discovery channels.

Category query styles:
- code: Implementation tech names, library names, algorithms. e.g. "pytorch transformer implementation", "self-attention github"
- academic: Paper-title style, include survey/review/analysis. e.g. "attention mechanism survey", "transformer architecture review 2023"
- discussion: Opinion/debate framing. e.g. "should I use transformer or RNN", "attention mechanism tradeoffs"
- product: App/service/product framing. e.g. "AI writing assistant app", "transformer based productivity tool"
- news: Recent developments, announcements. e.g. "transformer AI breakthrough", "LLM regulation policy news"

Respond with ONLY valid JSON. No markdown, no explanation."""


def _get_client() -> anthropic.AsyncAnthropic:
    global _client
    if _client is None:
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY not set")
        _client = anthropic.AsyncAnthropic(api_key=api_key, timeout=60.0)
    return _client


async def extract_concepts(input_text: str) -> dict[str, Any]:
    """
    Extract concepts and generate per-category query bundles from input text.
    Returns dict with: concepts, domain, domain_type, search_queries, query_bundles.
    """
    prompt = f"""Analyze this product/idea and return a JSON object:

Input: {input_text[:2000]}

Return JSON matching this exact schema:
{{
  "concepts": ["<concept1>", "<concept2>", ...],
  "domain": "<one-sentence domain description>",
  "domain_type": "<tech|research|consumer|business|healthcare|general>",
  "search_queries": ["<query1>", "<query2>"],
  "query_bundles": {{
    "code": ["<query>", ...],
    "academic": ["<query>", ...],
    "discussion": ["<query>", ...],
    "product": ["<query>", ...],
    "news": ["<query>", ...]
  }}
}}

Query count targets depend on domain_type:
{json.dumps(DOMAIN_QUERY_COUNTS, indent=2)}

Categories with 0 target count should be OMITTED from query_bundles entirely.
search_queries: always include 2-4 general queries as fallback.
Return ONLY the JSON object."""

    client = _get_client()
    try:
        msg = await client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2048,
            system=_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = msg.content[0].text.strip()
        raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.DOTALL).strip()
        result = json.loads(raw)
    except Exception as exc:
        logger.warning("extract_concepts failed: %s", exc)
        result = {}

    # Ensure required fields
    if "search_queries" not in result or not result["search_queries"]:
        words = input_text.split()[:6]
        result["search_queries"] = [" ".join(words)]
    else:
        result["search_queries"] = [str(query).strip() for query in result["search_queries"] if str(query).strip()]

    if "concepts" not in result:
        result["concepts"] = []
    if "domain" not in result:
        result["domain"] = input_text[:100]

    domain_type = result.get("domain_type", "general")
    if not isinstance(domain_type, str):
        domain_type = "general"
    domain_type = domain_type.strip().lower() or "general"
    query_targets = DOMAIN_QUERY_COUNTS.get(domain_type, DOMAIN_QUERY_COUNTS["general"])
    if domain_type not in DOMAIN_QUERY_COUNTS:
        logger.warning("Unknown domain_type %r from extractor; defaulting to general", domain_type)
        domain_type = "general"
    result["domain_type"] = domain_type

    raw_query_bundles = result.get("query_bundles", {})
    normalized_query_bundles: dict[str, list[str]] = {}
    if isinstance(raw_query_bundles, dict):
        for category, queries in raw_query_bundles.items():
            if query_targets.get(category, 0) <= 0 or not isinstance(queries, list):
                continue
            normalized_queries = [str(query).strip() for query in queries if str(query).strip()]
            if normalized_queries:
                normalized_query_bundles[category] = normalized_queries

    # Fallback if query_bundles missing or empty
    if not normalized_query_bundles:
        fallback_bundles: dict[str, list[str]] = {}
        for category in ("discussion", "code", "academic", "product", "news"):
            if query_targets.get(category, 0) > 0:
                fallback_bundles[category] = result["search_queries"]
        normalized_query_bundles = fallback_bundles or {"discussion": result["search_queries"]}
    result["query_bundles"] = normalized_query_bundles

    return result
