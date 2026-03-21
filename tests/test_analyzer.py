import pytest
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_cache_hit_calls_on_source_done():
    """on_source_done should be called per source group when cache is warm."""
    from backend.analyzer import analyze

    cached_items = [
        {"id": "a", "title": "GitHub repo", "source": "github", "score": 0.9},
        {"id": "b", "title": "HN post", "source": "hackernews", "score": 0.7},
        {"id": "c", "title": "HN post 2", "source": "hackernews", "score": 0.6},
    ]

    calls: list[tuple[str, list]] = []

    def on_source_done(source_name: str, items: list) -> None:
        calls.append((source_name, items))

    with patch("backend.analyzer.get_cached", return_value=cached_items):
        result = await analyze("test input", on_source_done=on_source_done)

    assert result == cached_items
    sources_called = {name for name, _ in calls}
    assert sources_called == {"github", "hackernews"}
    hn_items = next(items for name, items in calls if name == "hackernews")
    assert len(hn_items) == 2


@pytest.mark.asyncio
async def test_cache_hit_no_callback_still_returns():
    """Cache hit without on_source_done should work without error."""
    from backend.analyzer import analyze

    cached_items = [{"id": "a", "title": "T", "source": "github", "score": 0.5}]

    with patch("backend.analyzer.get_cached", return_value=cached_items):
        result = await analyze("test input", on_source_done=None)

    assert result == cached_items


@pytest.mark.asyncio
async def test_cache_miss_does_not_call_on_source_done_from_cache():
    """On cache miss, on_source_done is not called from the cache path."""
    from backend.analyzer import analyze

    calls: list[str] = []

    def on_source_done(source_name: str, items: list) -> None:
        calls.append(source_name)

    with patch("backend.analyzer.get_cached", return_value=None), \
         patch("backend.analyzer.extract_concepts", new_callable=AsyncMock,
               return_value={
                   "search_queries": ["test"],
                   "domain_type": "general",
                   "query_bundles": {},
               }), \
         patch("backend.analyzer.set_cache"):
        await analyze("test input", on_source_done=on_source_done)

    # No sources searched (empty query_bundles), so no callbacks
    assert calls == []
