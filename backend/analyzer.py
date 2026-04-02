from __future__ import annotations
import asyncio
import logging
from collections.abc import Callable
from types import ModuleType
from typing import Any, Coroutine

from backend.cache import get_cached, set_cache
from backend.extractor import extract_concepts
from backend.sources.models import RawItem

logger = logging.getLogger(__name__)

CATEGORY_SOURCES: dict[str, list[str]] = {
    "code":       ["github"],
    "academic":   ["arxiv", "semantic_scholar"],
    "discussion": ["hackernews", "reddit"],
    "product":    ["product_hunt", "itunes", "google_play"],
    "news":       ["gdelt", "serper"],
}

PROD_LIMITS: dict[str, int] = {
    "github":           60,
    "hackernews":       60,
    "reddit":           60,
    "arxiv":            60,
    "semantic_scholar": 60,
    "itunes":           40,
    "google_play":      40,
    "product_hunt":     40,
    "gdelt":            30,
    "serper":           20,
}


def _import_source(name: str) -> ModuleType:
    """Lazily import a source module."""
    import importlib
    return importlib.import_module(f"backend.sources.{name}")


async def _search_source(
    source_name: str,
    queries: list[str],
    *,
    limit: int,
    domain_type: str,
) -> list[Any]:
    try:
        mod = _import_source(source_name)
    except Exception as exc:
        logger.warning("Failed to load source %s: %s", source_name, exc)
        return []

    try:
        if source_name == "reddit":
            return await mod.search(queries, limit=limit, domain_type=domain_type)
        return await mod.search(queries, limit=limit)
    except Exception as exc:
        logger.warning("Source %s failed: %s", source_name, exc)
        return []


async def analyze(
    input_text: str,
    limits: dict[str, int] | None = None,
    on_source_done: Callable[[str, list[dict]], None] | None = None,
) -> list[dict[str, Any]]:
    """
    Full pipeline: cache check → concept extraction → parallel source search → cache write.
    Returns list of RawItem dicts.
    """
    cached = get_cached(input_text)
    if cached is not None:
        logger.info("Cache hit for input_text (len=%d)", len(input_text))
        if on_source_done is not None:
            by_source: dict[str, list[dict]] = {}
            for item in cached:
                by_source.setdefault(item.get("source", "unknown"), []).append(item)
            for source_name, items in by_source.items():
                on_source_done(source_name, items)
        return cached

    extraction = await extract_concepts(input_text)
    query_bundles: dict[str, list[str]] = extraction.get("query_bundles", {})
    domain_type: str = extraction.get("domain_type", "general")
    lim = {**PROD_LIMITS, **(limits or {})}

    # Build tasks for all sources (including GDELT)
    source_coroutines: list[Coroutine[Any, Any, list[Any]]] = []
    source_names_ordered: list[str] = []

    news_queries = query_bundles.get("news", [])

    for category, source_names in CATEGORY_SOURCES.items():
        queries = query_bundles.get(category, [])
        if not queries:
            continue
        for source_name in source_names:
            if source_name == "gdelt":
                # GDELT with custom timeout, but run in parallel with other sources
                try:
                    mod = _import_source("gdelt")
                except Exception as exc:
                    logger.warning("Failed to load source %s: %s", source_name, exc)
                    continue
                timeout_secs = len(news_queries) * 15 + 10
                gdelt_coro = asyncio.wait_for(
                    mod.search(news_queries, limit=lim["gdelt"]),
                    timeout=timeout_secs,
                )
                source_names_ordered.append("gdelt")
                source_coroutines.append(gdelt_coro)
                continue
            source_names_ordered.append(source_name)
            source_coroutines.append(
                _search_source(
                    source_name,
                    queries,
                    limit=lim[source_name],
                    domain_type=domain_type,
                )
            )

    # Run all sources in parallel (including GDELT)
    results_raw: list[Any] = []
    if source_coroutines:
        # Wrap each coroutine to fire the progress callback when it completes
        async def _wrap(coro: Coroutine, name: str) -> list[Any]:
            try:
                result = await coro
            except asyncio.TimeoutError:
                logger.warning("%s timed out", name)
                return []
            except Exception as exc:
                logger.warning("%s failed: %s", name, exc)
                return []
            if on_source_done is not None:
                dicts = [r.to_dict() if isinstance(r, RawItem) else r for r in result]
                on_source_done(name, dicts)
            return result

        wrapped = [_wrap(c, n) for c, n in zip(source_coroutines, source_names_ordered)]
        gathered = await asyncio.gather(*wrapped)
        for result in gathered:
            results_raw.extend(result)

    items = [item.to_dict() if isinstance(item, RawItem) else item for item in results_raw]

    # URL 기반 중복 제거 (소스 간)
    seen_urls: set[str] = set()
    deduplicated: list[dict[str, Any]] = []
    for item in items:
        url = item.get("url", "").strip().lower().rstrip("/")
        if url and url in seen_urls:
            continue
        if url:
            seen_urls.add(url)
        deduplicated.append(item)
    items = deduplicated

    set_cache(input_text, items)
    return items
