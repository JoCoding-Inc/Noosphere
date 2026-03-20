import asyncio
import logging
import xml.etree.ElementTree as ET
import httpx
from backend.sources.models import RawItem

logger = logging.getLogger(__name__)

_NS = {"atom": "http://www.w3.org/2005/Atom"}
_BASE_URL = "https://export.arxiv.org/api/query"


async def _fetch(query: str, limit: int) -> list[RawItem]:
    async with httpx.AsyncClient(timeout=20.0) as client:
        try:
            resp = await client.get(
                _BASE_URL,
                params={
                    "search_query": f"all:{query}",
                    "max_results": limit,
                    "sortBy": "relevance",
                },
            )
            resp.raise_for_status()
        except Exception as exc:
            logger.warning("arXiv request failed for query %r: %s", query, exc)
            return []
    try:
        root = ET.fromstring(resp.text)
    except ET.ParseError as exc:
        logger.warning("arXiv XML parsing failed for query %r: %s", query, exc)
        return []
    entries = root.findall("atom:entry", _NS)
    if not entries:
        return []
    items = []
    for entry in entries:
        arxiv_id = (entry.findtext("atom:id", "", _NS) or "").rstrip("/").split("/")[-1]
        arxiv_id = arxiv_id.split("v")[0]  # strip version
        title = (entry.findtext("atom:title", "", _NS) or "").strip().replace("\n", " ")
        summary = (entry.findtext("atom:summary", "", _NS) or "").strip()[:500]
        url = entry.findtext("atom:id", "", _NS) or ""
        date = entry.findtext("atom:published", "", _NS) or ""
        authors = [
            a.findtext("atom:name", "", _NS) or ""
            for a in entry.findall("atom:author", _NS)
        ][:3]
        if arxiv_id and title:
            items.append(
                RawItem(
                    id=f"arxiv:{arxiv_id}",
                    source="arxiv",
                    title=title,
                    url=url,
                    text=summary,
                    score=0.0,
                    date=date,
                    metadata={"authors": authors},
                )
            )
    return items


async def search(queries: list[str], limit: int) -> list[RawItem]:
    if not queries or limit <= 0:
        return []
    per_q = max(1, limit // len(queries))
    results = await asyncio.gather(
        *[_fetch(q, per_q) for q in queries], return_exceptions=True
    )
    seen, items = set(), []
    for batch in results:
        if isinstance(batch, Exception):
            continue
        for item in batch:
            if item.id not in seen:
                seen.add(item.id)
                items.append(item)
    return items[:limit]
