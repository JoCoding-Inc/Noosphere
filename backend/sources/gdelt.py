import asyncio
import logging
from hashlib import sha1
import httpx
from backend.sources.models import RawItem

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.gdeltproject.org/api/v2/doc/doc"


async def _fetch(query: str, limit: int) -> list[RawItem]:
    params = {
        "query": query,
        "mode": "artlist",
        "maxrecords": limit,
        "format": "json",
        "timespan": "1year",
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.get(_BASE_URL, params=params)
            resp.raise_for_status()
        except Exception as exc:
            logger.warning("GDELT request failed for query %r: %s", query, exc)
            return []
    try:
        data = resp.json()
    except Exception as exc:
        logger.warning("GDELT JSON parsing failed for query %r: %s", query, exc)
        return []
    articles = data.get("articles")
    if not isinstance(articles, list):
        logger.warning("GDELT response missing articles list for query %r", query)
        return []
    items = []
    for index, article in enumerate(articles):
        url = article.get("url", "")
        if url:
            item_id = f"gdelt:{url[-60:]}"
        else:
            fallback_key = "|".join(
                [
                    query,
                    article.get("title") or "",
                    article.get("seendate") or "",
                    str(index),
                ]
            )
            item_id = f"gdelt:fallback:{sha1(fallback_key.encode('utf-8')).hexdigest()[:16]}"
        title = article.get("title", "")
        seendate = article.get("seendate") or ""
        domain = article.get("domain") or ""
        text = f"{seendate} {domain}".strip()
        date = article.get("seendate", "")
        language = article.get("language", "")
        items.append(
            RawItem(
                id=item_id,
                source="gdelt",
                title=title,
                url=url,
                text=text,
                score=0.0,
                date=date,
                metadata={"domain": domain, "language": language},
            )
        )
    return items


async def search(queries: list[str], limit: int) -> list[RawItem]:
    if not queries or limit <= 0:
        return []
    per_q = max(1, limit // len(queries))
    seen, items = set(), []
    for i, query in enumerate(queries):
        if i > 0:
            await asyncio.sleep(10)  # rate limit: ~1 req/5s, use 10s to be safe
        try:
            batch = await _fetch(query, per_q)
        except Exception as exc:
            logger.warning("GDELT query %r failed: %s", query, exc)
            continue
        for item in batch:
            if item.id not in seen:
                seen.add(item.id)
                items.append(item)
    return items[:limit]
