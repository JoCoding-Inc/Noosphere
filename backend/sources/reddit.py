import asyncio
import logging

import httpx

from backend.sources.models import RawItem

logger = logging.getLogger(__name__)

_BASE_URL = "https://www.reddit.com/r/{subreddit}/search.json"
_HEADERS = {"User-Agent": "noosphere-research/1.0"}

SUBREDDITS_BY_DOMAIN = {
    "tech":       ["programming", "technology", "compsci", "MachineLearning"],
    "research":   ["MachineLearning", "artificial", "science", "compsci"],
    "consumer":   ["apps", "software", "productivity", "SideProject"],
    "business":   ["startups", "entrepreneur", "business", "SaaS"],
    "healthcare": ["health", "medicine", "medical", "healthIT"],
    "general":    ["startups", "technology", "programming", "entrepreneur"],
}


async def _fetch_subreddit(query: str, subreddit: str, per_sub_limit: int) -> list[RawItem]:
    url = _BASE_URL.format(subreddit=subreddit)
    params = {
        "q": query,
        "sort": "relevance",
        "limit": per_sub_limit,
        "restrict_sr": "true",
        "t": "year",
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(url, headers=_HEADERS, params=params)

    if response.status_code == 429:
        logger.warning(
            "Reddit rate limit hit for query %r in subreddit %r",
            query,
            subreddit,
        )
        return []

    response.raise_for_status()
    try:
        data = response.json()
    except ValueError as exc:
        logger.warning(
            "Reddit returned invalid JSON for query %r in subreddit %r: %s",
            query,
            subreddit,
            exc,
        )
        return []

    if not isinstance(data, dict):
        logger.warning(
            "Reddit returned non-object JSON for query %r in subreddit %r",
            query,
            subreddit,
        )
        return []

    payload = data.get("data")
    if not isinstance(payload, dict):
        logger.warning(
            "Reddit returned invalid data payload for query %r in subreddit %r",
            query,
            subreddit,
        )
        return []

    children = payload.get("children", [])
    if not isinstance(children, list):
        logger.warning(
            "Reddit returned invalid children payload for query %r in subreddit %r",
            query,
            subreddit,
        )
        return []

    items: list[RawItem] = []
    for post in children:
        if not isinstance(post, dict):
            continue
        post_data = post.get("data")
        if not isinstance(post_data, dict):
            continue
        post_id = post_data.get("id")
        title = post_data.get("title")
        permalink = post_data.get("permalink")
        subreddit_name = post_data.get("subreddit")
        if not post_id or not title or not permalink or not subreddit_name:
            continue
        items.append(
            RawItem(
                id=f"reddit:{post_id}",
                source="reddit",
                title=title,
                url=f"https://reddit.com{permalink}",
                text=(post_data.get("selftext") or "")[:500],
                score=float(post_data.get("score") or 0),
                date=str(post_data.get("created_utc") or ""),
                metadata={
                    "subreddit": subreddit_name,
                    "num_comments": post_data.get("num_comments", 0),
                },
            )
        )
    return items


async def search(
    queries: list[str], limit: int, domain_type: str = "general"
) -> list[RawItem]:
    subreddits = SUBREDDITS_BY_DOMAIN.get(domain_type, SUBREDDITS_BY_DOMAIN["general"])
    per_sub = max(1, limit // (len(queries) * len(subreddits)))
    seen: set[str] = set()
    items: list[RawItem] = []

    for query in queries:
        batch_results = await asyncio.gather(
            *[_fetch_subreddit(query, sub, per_sub) for sub in subreddits],
            return_exceptions=True,
        )
        for batch in batch_results:
            if isinstance(batch, Exception):
                logger.warning("Reddit fetch error for query %r: %s", query, batch)
                continue
            for item in batch:
                if item.id not in seen:
                    seen.add(item.id)
                    items.append(item)

    return items[:limit]
