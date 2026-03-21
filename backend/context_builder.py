from __future__ import annotations
import json
import logging
import re
import uuid

import httpx

from backend import llm

logger = logging.getLogger(__name__)


async def extract_concepts_from_text(text: str, provider: str = "openai") -> list[str]:
    """Use OpenAI to extract key concepts/entities from product description."""
    prompt = (
        f"Extract 5-10 key concepts, technologies, or market categories from this "
        f"product description. Return ONLY a JSON array of strings.\n\n{text[:2000]}"
    )
    response = await llm.complete(
        messages=[{"role": "user", "content": prompt}],
        tier="low",
        provider=provider,
        max_tokens=512,
    )
    raw = (response.content or "").strip()
    if not raw:
        return []
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.DOTALL).strip()
    try:
        concepts = json.loads(raw)
        return [str(c) for c in concepts if c][:10]
    except json.JSONDecodeError:
        return [c.strip(' "') for c in re.split(r"[,\n]", raw) if c.strip(' "')][:10]


async def _fetch_hn_posts(query: str, limit: int = 5) -> list[dict]:
    """Fetch related HN posts for a concept query."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                "https://hn.algolia.com/api/v1/search",
                params={"query": query, "tags": "story", "hitsPerPage": limit},
            )
            resp.raise_for_status()
            hits = resp.json().get("hits", [])
            return [
                {
                    "id": str(uuid.uuid4()),
                    "title": h.get("title", query)[:200],
                    "source": "hackernews",
                    "abstract": (h.get("story_text") or h.get("title", ""))[:300],
                }
                for h in hits
                if h.get("title")
            ]
    except Exception as exc:
        logger.warning("HN fetch failed for %r: %s", query, exc)
        return []


def _nodes_from_concepts(text: str, concepts: list[str]) -> list[dict]:
    """Create context nodes from extracted concepts using the input text as abstract source."""
    text_snippet = text[:300].replace("\n", " ")
    nodes = []
    for concept in concepts:
        nodes.append({
            "id": str(uuid.uuid4()),
            "title": concept,
            "source": "input_text",
            "abstract": f"{concept} — extracted from: {text_snippet}",
        })
    return nodes


async def build_context_nodes(
    input_text: str,
    enrich: bool = True,
    max_nodes: int = 30,
    provider: str = "openai",
) -> list[dict]:
    """
    Main entry point. Returns list of context node dicts for the simulation engine.

    Args:
        input_text: Raw product/service description from user
        enrich: If True, fetch related HN posts to augment context
        max_nodes: Cap on total nodes returned
        provider: LLM provider to use
    """
    concepts = await extract_concepts_from_text(input_text, provider=provider)
    nodes = _nodes_from_concepts(input_text, concepts)

    if enrich and concepts:
        import asyncio
        tasks = [_fetch_hn_posts(c, limit=3) for c in concepts[:3]]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for r in results:
            if isinstance(r, list):
                nodes.extend(r)

    seen_titles: set[str] = set()
    deduped = []
    for n in nodes:
        t = n["title"].lower()
        if t not in seen_titles:
            seen_titles.add(t)
            deduped.append(n)

    return deduped[:max_nodes]


async def detect_domain(input_text: str, provider: str = "openai") -> str:
    """Detect the product domain (e.g. 'SaaS', 'fintech', 'developer tools')."""
    prompt = (
        f"In 2-4 words, what is the domain of this product? "
        f"Examples: 'developer tools', 'B2B SaaS', 'fintech', 'consumer app'.\n\n"
        f"Reply with only the domain string.\n\n{input_text[:500]}"
    )
    try:
        response = await llm.complete(
            messages=[{"role": "user", "content": prompt}],
            tier="low",
            provider=provider,
            max_tokens=32,
        )
        return (response.content or "").strip()[:50] or "technology"
    except Exception:
        return "technology"
