import asyncio
import logging

import httpx

from backend.sources.models import RawItem

logger = logging.getLogger(__name__)

_BASE_URL = "https://hn.algolia.com/api/v1/search"


async def _fetch(query: str, per_q: int) -> list[RawItem]:
    params = {"query": query, "tags": "story", "hitsPerPage": per_q}

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(_BASE_URL, params=params)

    response.raise_for_status()
    try:
        data = response.json()
    except ValueError as exc:
        logger.warning("Hacker News returned invalid JSON for query %r: %s", query, exc)
        return []

    if not isinstance(data, dict):
        logger.warning("Hacker News returned non-object JSON for query %r", query)
        return []

    hits = data.get("hits")
    if not hits:
        logger.info("Hacker News returned no hits for query %r", query)
        return []
    if not isinstance(hits, list):
        logger.warning("Hacker News returned invalid hits payload for query %r", query)
        return []

    items: list[RawItem] = []
    for hit in hits:
        if not isinstance(hit, dict):
            continue
        object_id = hit.get("objectID")
        title = hit.get("title")
        if not object_id or not title:
            continue
        items.append(
            RawItem(
                id=f"hackernews:{object_id}",
                source="hackernews",
                title=title,
                url=hit.get("url") or f"https://news.ycombinator.com/item?id={object_id}",
                text=(hit.get("story_text") or "")[:500],
                score=float(hit.get("points") or 0),
                date=hit.get("created_at") or "",
                metadata={"num_comments": hit.get("num_comments", 0)},
            )
        )
    return items


async def search(queries: list[str], limit: int) -> list[RawItem]:
    per_q = max(1, limit // len(queries))
    results = await asyncio.gather(
        *[_fetch(q, per_q) for q in queries], return_exceptions=True
    )
    seen: set[str] = set()
    items: list[RawItem] = []
    for batch in results:
        if isinstance(batch, Exception):
            logger.warning("Hacker News fetch error: %s", batch)
            continue
        for item in batch:
            if item.id not in seen:
                seen.add(item.id)
                items.append(item)
    return items[:limit]
