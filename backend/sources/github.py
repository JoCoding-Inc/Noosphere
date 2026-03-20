import asyncio
import logging
import os

import httpx

from backend.sources.models import RawItem

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.github.com/search/repositories"


async def _fetch(query: str, per_q: int) -> list[RawItem]:
    headers: dict[str, str] = {"Accept": "application/vnd.github+json"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    params = {"q": query, "per_page": per_q, "sort": "stars"}

    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.get(_BASE_URL, headers=headers, params=params)

    if response.status_code in (403, 429):
        logger.warning(
            "GitHub rate limit hit (status %d) for query %r", response.status_code, query
        )
        return []

    response.raise_for_status()
    try:
        data = response.json()
    except ValueError as exc:
        logger.warning("GitHub returned invalid JSON for query %r: %s", query, exc)
        return []

    if not isinstance(data, dict):
        logger.warning("GitHub returned non-object JSON for query %r", query)
        return []

    raw_items = data.get("items")
    if not isinstance(raw_items, list):
        logger.warning("GitHub response missing items list for query %r", query)
        return []

    items: list[RawItem] = []
    for repo in raw_items:
        if not isinstance(repo, dict):
            continue
        full_name = repo.get("full_name")
        html_url = repo.get("html_url")
        if not full_name or not html_url:
            continue
        items.append(
            RawItem(
                id=f"github:{full_name}",
                source="github",
                title=full_name,
                url=html_url,
                text=repo.get("description") or "",
                score=float(repo.get("stargazers_count") or 0),
                date=repo.get("pushed_at") or "",
                metadata={
                    "language": repo.get("language"),
                    "forks": repo.get("forks_count", 0),
                },
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
            logger.warning("GitHub fetch error: %s", batch)
            continue
        for item in batch:
            if item.id not in seen:
                seen.add(item.id)
                items.append(item)
    return items[:limit]
