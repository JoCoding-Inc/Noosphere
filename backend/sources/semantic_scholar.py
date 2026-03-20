import asyncio
import logging
import os
import httpx
from backend.sources.models import RawItem

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.semanticscholar.org/graph/v1/paper/search"


async def _fetch(query: str, limit: int) -> list[RawItem]:
    headers = {"x-api-key": os.environ.get("SEMANTIC_SCHOLAR_API_KEY", "")}
    params = {
        "query": query,
        "limit": limit,
        "fields": "title,abstract,year,authors,url,citationCount,externalIds",
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            resp = await client.get(_BASE_URL, headers=headers, params=params)
            if resp.status_code == 429:
                logger.warning("Semantic Scholar rate limit hit for query %r", query)
                return []
            resp.raise_for_status()
        except Exception as exc:
            logger.warning("Semantic Scholar request failed for query %r: %s", query, exc)
            return []
    try:
        data = resp.json()
    except Exception as exc:
        logger.warning("Semantic Scholar JSON parsing failed for query %r: %s", query, exc)
        return []
    papers = data.get("data")
    if not isinstance(papers, list):
        logger.warning("Semantic Scholar response missing data list for query %r", query)
        return []
    items = []
    for paper in papers:
        paper_id = paper.get("paperId", "")
        if not paper_id:
            continue
        title = paper.get("title") or ""
        url = paper.get("url") or f"https://www.semanticscholar.org/paper/{paper_id}"
        text = (paper.get("abstract") or "")[:500]
        score = float(paper.get("citationCount") or 0)
        date = str(paper.get("year") or "")
        authors = [
            author.get("name", "")
            for author in paper.get("authors", [])[:3]
            if author.get("name")
        ]
        external_ids = paper.get("externalIds", {})
        items.append(
            RawItem(
                id=f"semantic_scholar:{paper_id}",
                source="semantic_scholar",
                title=title,
                url=url,
                text=text,
                score=score,
                date=date,
                metadata={"authors": authors, "externalIds": external_ids},
            )
        )
    return items


async def search(queries: list[str], limit: int) -> list[RawItem]:
    if not queries or limit <= 0:
        return []
    per_q = max(1, limit // len(queries))
    seen, items = set(), []
    for i, q in enumerate(queries):
        if i > 0:
            await asyncio.sleep(1.5)
        batch = await _fetch(q, per_q)
        for item in batch:
            if item.id not in seen:
                seen.add(item.id)
                items.append(item)
    return items[:limit]
