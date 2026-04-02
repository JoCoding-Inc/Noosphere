from __future__ import annotations
import hashlib
import json
import logging
import os
import re
import sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path
from threading import Lock
from typing import Any

logger = logging.getLogger(__name__)

DB_PATH = Path(os.environ.get("SOURCES_DB_PATH", str(Path(__file__).parent.parent / "noosphere_sources.db")))
TTL_DAYS = 7
_SCHEMA_VERSION = 2
_initialized_paths: set[Path] = set()
_init_lock = Lock()


def _conn(path: Path = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def _normalize_path(path: Path = DB_PATH) -> Path:
    return Path(path).expanduser().resolve()


def init_cache(path: Path = DB_PATH) -> None:
    """Initialize cache DB and run schema migration if needed."""
    path = _normalize_path(path)
    logger.debug("Initializing cache DB at %s", path)
    with _conn(path) as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS source_cache (
                query_hash TEXT PRIMARY KEY,
                input_text TEXT NOT NULL,
                results_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                schema_version INTEGER NOT NULL DEFAULT 2
            );
        """)
        # Migration: purge rows from old schema (keyed by sorted-query hash)
        conn.execute(
            "DELETE FROM source_cache WHERE LENGTH(query_hash) != 64 OR schema_version < 2"
        )


def _ensure_initialized(path: Path = DB_PATH) -> Path:
    normalized_path = _normalize_path(path)
    if normalized_path in _initialized_paths:
        return normalized_path

    with _init_lock:
        if normalized_path not in _initialized_paths:
            init_cache(normalized_path)
            _initialized_paths.add(normalized_path)
    return normalized_path


def _normalize_input(text: str) -> str:
    """Normalize input text for cache key: lowercase, strip punctuation, collapse whitespace."""
    text = text.lower().strip()
    text = re.sub(r'[^\w\s]', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text


def _hash(input_text: str) -> str:
    return hashlib.sha256(_normalize_input(input_text).encode()).hexdigest()


def get_cached(input_text: str, path: Path = DB_PATH) -> list[dict[str, Any]] | None:
    path = _ensure_initialized(path)
    key = _hash(input_text)
    cutoff = (datetime.now(timezone.utc) - timedelta(days=TTL_DAYS)).isoformat()
    with _conn(path) as conn:
        row = conn.execute(
            "SELECT results_json, created_at FROM source_cache WHERE query_hash=?",
            (key,)
        ).fetchone()
    if not row:
        return None
    if row["created_at"] < cutoff:
        # Expired
        with _conn(path) as conn:
            conn.execute("DELETE FROM source_cache WHERE query_hash=?", (key,))
        return None
    return json.loads(row["results_json"])


def set_cache(input_text: str, results: list[dict[str, Any]], path: Path = DB_PATH) -> None:
    path = _ensure_initialized(path)
    key = _hash(input_text)
    now = datetime.now(timezone.utc).isoformat()
    with _conn(path) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO source_cache VALUES (?,?,?,?,?)",
            (key, input_text.strip(), json.dumps(results, ensure_ascii=False), now, _SCHEMA_VERSION)
        )
