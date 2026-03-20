from __future__ import annotations

import asyncio
import logging

import httpx

from backend.sources.models import RawItem

logger = logging.getLogger(__name__)

_SEARCH_URL = "https://itunes.apple.com/search"


async def search(queries: list[str], limit: int) -> list[RawItem]:
    if not queries or limit <= 0:
        return []

    per_q = max(1, limit // len(queries))
    results = await asyncio.gather(
        *[_fetch(q, per_q) for q in queries],
        return_exceptions=True,
    )
    seen, items = set(), []
    for batch in results:
        if isinstance(batch, Exception):
            logger.warning("itunes fetch error: %s", batch)
            continue
        for item in batch:
            if item.id not in seen:
                seen.add(item.id)
                items.append(item)
    return items[:limit]


async def _fetch(query: str, limit: int) -> list[RawItem]:
    params = {
        "term": query,
        "limit": limit,
        "entity": "software",
        "country": "us",
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(_SEARCH_URL, params=params)
        response.raise_for_status()
        try:
            data = response.json()
        except ValueError as exc:
            logger.warning("iTunes returned invalid JSON for query %r: %s", query, exc)
            return []

    if not isinstance(data, dict):
        logger.warning("iTunes returned non-object JSON for query %r", query)
        return []

    raw_results = data.get("results")
    if not isinstance(raw_results, list):
        logger.warning("iTunes response missing results list for query %r", query)
        return []

    items: list[RawItem] = []
    for result in raw_results:
        if not isinstance(result, dict):
            continue
        track_id = result.get("trackId")
        if track_id is None:
            continue
        try:
            score = float(result.get("averageUserRating") or 0)
        except (TypeError, ValueError):
            score = 0.0
        items.append(
            RawItem(
                id=f"itunes:{track_id}",
                source="itunes",
                title=result.get("trackName", ""),
                url=result.get("trackViewUrl", ""),
                text=(result.get("description") or "")[:500],
                score=score,
                date=result.get("releaseDate") or "",
                metadata={
                    "developer": result.get("artistName", ""),
                    "price": result.get("formattedPrice", ""),
                    "genre": result.get("primaryGenreName", ""),
                    "rating_count": result.get("userRatingCount", 0),
                },
            )
        )
    return items
