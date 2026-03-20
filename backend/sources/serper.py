from __future__ import annotations

import asyncio
import logging
import os

import httpx

from backend.sources.models import RawItem

logger = logging.getLogger(__name__)

_SEARCH_URL = "https://google.serper.dev/search"


async def search(queries: list[str], limit: int) -> list[RawItem]:
    if not queries or limit <= 0:
        return []

    api_key = os.getenv("SERPER_API_KEY")
    if not api_key:
        logger.warning("SERPER_API_KEY not set; skipping Serper source")
        return []

    per_q = max(1, limit // len(queries))
    results = await asyncio.gather(
        *[_fetch(q, per_q, api_key) for q in queries],
        return_exceptions=True,
    )
    seen, items = set(), []
    for batch in results:
        if isinstance(batch, Exception):
            logger.warning("serper fetch error: %s", batch)
            continue
        for item in batch:
            if item.id not in seen:
                seen.add(item.id)
                items.append(item)
    return items[:limit]


async def _fetch(query: str, limit: int, api_key: str) -> list[RawItem]:
    headers = {
        "X-API-KEY": api_key,
        "Content-Type": "application/json",
    }
    payload = {"q": query, "num": limit}

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(_SEARCH_URL, json=payload, headers=headers)
        response.raise_for_status()
        try:
            data = response.json()
        except ValueError as exc:
            logger.warning("Serper returned invalid JSON for query %r: %s", query, exc)
            return []

    if not isinstance(data, dict):
        logger.warning("Serper returned non-object JSON for query %r", query)
        return []

    organic_results = data.get("organic")
    if not isinstance(organic_results, list):
        logger.warning("Serper response missing organic list for query %r", query)
        return []

    items: list[RawItem] = []
    for result in organic_results:
        if not isinstance(result, dict):
            continue
        link = result.get("link", "")
        try:
            position = float(result.get("position", 99))
        except (TypeError, ValueError):
            position = 99.0
        score = 1.0 / (position + 1)
        items.append(
            RawItem(
                id=f"serper:{link[-60:]}",
                source="serper",
                title=result.get("title", ""),
                url=link,
                text=result.get("snippet", "")[:500],
                score=score,
                date=result.get("date", ""),
                metadata={"domain": result.get("domain", "")},
            )
        )
    return items
