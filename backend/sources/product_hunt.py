from __future__ import annotations

import asyncio
import logging
import os

import httpx

from backend.sources.models import RawItem

logger = logging.getLogger(__name__)

_GQL_URL = "https://api.producthunt.com/v2/api/graphql"

_QUERY = """
query SearchPosts($query: String!, $first: Int!) {
  posts(query: $query, order: VOTES, first: $first) {
    edges {
      node {
        id
        name
        tagline
        description
        url
        votesCount
        createdAt
        topics { edges { node { name } } }
      }
    }
  }
}
"""


async def search(queries: list[str], limit: int) -> list[RawItem]:
    if not queries or limit <= 0:
        return []

    api_key = os.getenv("PRODUCT_HUNT_API_KEY")
    if not api_key:
        logger.warning("PRODUCT_HUNT_API_KEY not set; skipping Product Hunt source")
        return []

    per_q = max(1, limit // len(queries))
    results = await asyncio.gather(
        *[_fetch(q, per_q, api_key) for q in queries],
        return_exceptions=True,
    )
    seen, items = set(), []
    for batch in results:
        if isinstance(batch, Exception):
            logger.warning("product_hunt fetch error: %s", batch)
            continue
        for item in batch:
            if item.id not in seen:
                seen.add(item.id)
                items.append(item)
    return items[:limit]


async def _fetch(query: str, limit: int, api_key: str) -> list[RawItem]:
    payload = {
        "query": _QUERY,
        "variables": {"query": query, "first": limit},
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(_GQL_URL, json=payload, headers=headers)
        response.raise_for_status()
        try:
            data = response.json()
        except ValueError as exc:
            logger.warning(
                "Product Hunt returned invalid JSON for query %r: %s", query, exc
            )
            return []

    if not isinstance(data, dict):
        logger.warning("Product Hunt returned non-object JSON for query %r", query)
        return []

    errors = data.get("errors")
    if errors:
        logger.warning(
            "Product Hunt returned GraphQL errors for query %r: %s", query, errors
        )
        return []

    payload_data = data.get("data")
    if not isinstance(payload_data, dict):
        logger.warning("Product Hunt response missing data object for query %r", query)
        return []

    posts = payload_data.get("posts")
    if not isinstance(posts, dict):
        logger.warning("Product Hunt response missing posts object for query %r", query)
        return []

    edges = posts.get("edges")
    if not isinstance(edges, list):
        logger.warning("Product Hunt response missing edges list for query %r", query)
        return []

    items: list[RawItem] = []
    for edge in edges:
        if not isinstance(edge, dict):
            continue
        node = edge.get("node", {})
        if not isinstance(node, dict):
            continue
        node_id = node.get("id")
        if not node_id:
            continue
        tagline = node.get("tagline") or ""
        description = (node.get("description") or "")[:400]
        text = f"{tagline} {description}".strip()
        topics_payload = node.get("topics")
        if not isinstance(topics_payload, dict):
            topics_payload = {}
        topic_edges = topics_payload.get("edges", [])
        if not isinstance(topic_edges, list):
            topic_edges = []
        try:
            score = float(node.get("votesCount") or 0)
        except (TypeError, ValueError):
            score = 0.0
        topics = [
            e["node"]["name"]
            for e in topic_edges
            if isinstance(e, dict)
            and isinstance(e.get("node"), dict)
            and e["node"].get("name")
        ]
        items.append(
            RawItem(
                id=f"product_hunt:{node_id}",
                source="product_hunt",
                title=node.get("name", ""),
                url=node.get("url", ""),
                text=text,
                score=score,
                date=node.get("createdAt") or "",
                metadata={"topics": topics},
            )
        )
    return items
