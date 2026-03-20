from __future__ import annotations

import asyncio
import logging

from backend.sources.models import RawItem

logger = logging.getLogger(__name__)


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
            logger.warning("google_play fetch error: %s", batch)
            continue
        for item in batch:
            if item.id not in seen:
                seen.add(item.id)
                items.append(item)
    return items[:limit]


async def _fetch(query: str, limit: int) -> list[RawItem]:
    try:
        from google_play_scraper import search as gps_search
    except ImportError:
        logger.warning("google_play_scraper not installed; skipping Google Play source")
        return []

    try:
        loop = asyncio.get_running_loop()
        results = await loop.run_in_executor(
            None,
            lambda: gps_search(query, n_hits=limit, lang="en", country="us"),
        )
    except Exception as exc:
        logger.warning("google_play search failed for %r: %s", query, exc)
        return []

    if not isinstance(results, list):
        logger.warning("google_play returned invalid results for query %r", query)
        return []

    items: list[RawItem] = []
    for result in results:
        if not isinstance(result, dict):
            continue
        app_id = result.get("appId")
        if not app_id:
            continue
        try:
            score = float(result.get("score") or 0)
        except (TypeError, ValueError):
            score = 0.0
        items.append(
            RawItem(
                id=f"google_play:{app_id}",
                source="google_play",
                title=result.get("title", ""),
                url=f"https://play.google.com/store/apps/details?id={app_id}",
                text=(result.get("description") or "")[:500],
                score=score,
                date=result.get("released") or "",
                metadata={
                    "developer": result.get("developer", ""),
                    "installs": result.get("installs", ""),
                    "genre": result.get("genre", ""),
                },
            )
        )
    return items
