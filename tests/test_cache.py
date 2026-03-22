from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from backend import cache


def test_cache_initializes_once_for_same_db_with_relative_and_absolute_paths(tmp_path, monkeypatch):
    cache._initialized_paths.clear()
    monkeypatch.chdir(tmp_path)

    db_path_relative = Path("cache.db")
    db_path_absolute = db_path_relative.resolve()
    init_calls = 0
    original_init_cache = cache.init_cache

    def counting_init(path: Path = cache.DB_PATH) -> None:
        nonlocal init_calls
        init_calls += 1
        original_init_cache(path)

    with patch("backend.cache.init_cache", side_effect=counting_init):
        assert cache.get_cached("hello", path=db_path_relative) is None
        cache.set_cache("hello", [{"title": "world"}], path=db_path_absolute)
        assert cache.get_cached("hello", path=db_path_relative) == [{"title": "world"}]

    assert init_calls == 1


def test_cache_initializes_once_under_concurrent_access(tmp_path):
    cache._initialized_paths.clear()

    db_path = tmp_path / "cache.db"
    init_calls = 0
    original_init_cache = cache.init_cache

    def counting_init(path: Path = cache.DB_PATH) -> None:
        nonlocal init_calls
        init_calls += 1
        original_init_cache(path)

    with patch("backend.cache.init_cache", side_effect=counting_init):
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda _: cache.get_cached("hello", path=db_path), range(4)))

    assert results == [None, None, None, None]
    assert init_calls == 1
