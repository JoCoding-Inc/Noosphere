# Per-Platform Query Bundle Design

**Date:** 2026-03-20
**Status:** Draft

**Scope:** `backend/extractor.py`, `backend/analyzer.py`, `backend/cache.py`, all source files under `backend/sources/`

---

## Problem

All sources currently receive the same two queries joined into a single string (`" ".join(queries[:2])`). A GitHub code search and a Product Hunt product search require fundamentally different query vocabulary. This produces low-quality results, especially for non-tech domains.

Additionally, only 2 queries are sent per source, missing semantically related concepts (e.g. searching only "attention mechanism" but not "transformer", "self-attention", "BERT").

---

## Design

### 1. Category-Based Query Bundles

`extractor.py` generates per-category query bundles in a single Claude call. The new schema keeps `search_queries` as a required field (used as fallback) and adds `query_bundles`:

```json
{
  "concepts": ["attention mechanism", "transformer", "self-attention"],
  "domain": "Neural network architecture for sequence modeling",
  "domain_type": "research",
  "search_queries": ["attention mechanism transformer", "self-attention neural network"],
  "query_bundles": {
    "code":       ["transformer self-attention pytorch", "multi-head attention implementation"],
    "academic":   ["attention mechanism survey neural network", "scaled dot-product attention paper", "transformer architecture review", "BERT GPT self-attention study", "sequence to sequence attention model", "attention is all you need analysis"],
    "discussion": ["attention is all you need impact discussion", "transformer vs RNN tradeoffs"],
    "news":       ["transformer architecture AI news", "large language model attention breakthrough"]
  }
}
```

Categories with 0 queries for a given domain are omitted from `query_bundles`.

**Fallback:** If Claude omits `query_bundles` from the extraction response, `extract_concepts()` constructs a synthetic bundle: `{"discussion": search_queries, "code": search_queries}`. `search_queries` is always present (kept as required field), so this fallback is always valid.

### 2. Category → Source Mapping

`domain_type`-based per-source gating flags (`USE_GITHUB`, `USE_HN`, etc.) are **replaced** by `CATEGORY_SOURCES` routing. A source only runs if its category appears in `query_bundles`. This is the single gate.

```python
CATEGORY_SOURCES = {
    "code":       ["github"],
    "academic":   ["arxiv", "semantic_scholar"],
    "discussion": ["hackernews", "reddit"],
    "product":    ["product_hunt", "itunes", "google_play"],
    "news":       ["gdelt", "serper"],
}
```

### 3. Domain-Adaptive Query Counts

Claude generates queries within these per-category target counts. Claude may adjust within ±1 based on the idea, but must never exceed 2× the target.

| domain_type | code | academic | discussion | product | news |
|---|---|---|---|---|---|
| tech        | 5    | 5        | 3          | 2       | 1    |
| research    | 2    | 6        | 2          | 0       | 2    |
| consumer    | 1    | 0        | 3          | 5       | 2    |
| business    | 2    | 0        | 2          | 4       | 3    |
| healthcare  | 2    | 5        | 2          | 1       | 3    |
| general     | 2    | 2        | 3          | 2       | 3    |

### 4. Per-Query Parallel Execution

Each source receives the query list for its category and executes each query as a **separate parallel API call**, then deduplicates by item ID.

`limit` is distributed evenly: `per_query_limit = max(1, limit // len(queries))`. Total results may be slightly less than `limit` after dedup — breadth of coverage is prioritised over hitting an exact count. `PROD_LIMITS` are raised to compensate (see revised table below).

**Interface (unchanged signature, changed internal behavior):**
```python
async def search(queries: list[str], limit: int) -> list[RawItem]:
    per_q = max(1, limit // len(queries))
    results = await asyncio.gather(*[_fetch(q, per_q) for q in queries],
                                   return_exceptions=True)
    seen, items = set(), []
    for batch in results:
        if isinstance(batch, Exception):
            continue
        for item in batch:
            if item.id not in seen:
                seen.add(item.id)
                items.append(item)
    return items[:limit]
```

**Revised PROD_LIMITS** (raised to account for per-query distribution):

| Source | Current | New |
|---|---|---|
| github | 30 | 60 |
| hackernews | 50 | 60 |
| reddit | 40 | 60 |
| arxiv | 30 | 60 |
| semantic_scholar | 30 | 60 |
| itunes | 20 | 40 |
| google_play | 20 | 40 |
| product_hunt | 20 | 40 |
| gdelt | 30 | 30 (unchanged — rate limited) |
| serper | 10 | 20 |

**GitHub special case:** `github.py` currently caps queries at `queries[:3]` due to GitHub's OR-chain search limit per request. Under the new design, each query is a separate request, so this cap is removed.

**Reddit special case:** Reddit already parallelises across subreddits. Under the new design, queries are iterated **sequentially**, and subreddits are parallelised per query (the existing behaviour). `domain_type` continues to be passed to `reddit.search()` as a keyword argument to preserve subreddit selection. Total requests = `len(queries) × len(subreddits)`.

**GDELT special case:** GDELT enforces ~1 req/5s. Sequential per-query execution with 10s delay between queries lives **inside `gdelt.search()`** (not in `analyzer.py`). `analyzer.py` wraps the GDELT coroutine with its own timeout, separate from the main `asyncio.gather`:

```python
# In analyzer.py
news_queries = query_bundles.get("news", [])
gdelt_timeout = len(news_queries) * 15 + 10  # seconds
gdelt_coro = asyncio.wait_for(gdelt.search(news_queries, limit=lim["gdelt"]),
                               timeout=gdelt_timeout)
# gdelt_coro is added to gather separately from other sources
```

### 5. Cache Key Change

| | Current | New |
|---|---|---|
| Signature | `get_cached(queries: list[str])` | `get_cached(input_text: str)` |
| Key | `hash(sorted(queries))` | `hash(input_text.strip().lower())` |
| Why | Queries change with new bundle design | Input text is stable; same idea → same cache |

`cache.py` function signatures change: `get_cached(input_text: str)` and `set_cache(input_text: str, results: list[dict])`. `analyzer.py` passes the original user input text to both calls.

**Stale rows:** Existing cache rows keyed by query-hash will never match new lookups and accumulate as dead rows. They will not be purged by the TTL path (which requires a lookup hit). On startup, `cache.py` runs a one-time migration: `DELETE FROM source_cache WHERE LENGTH(query_hash) != 64` — old SHA-256 hashes are 64 hex chars; the new key format is also SHA-256 but collision with old rows is possible in theory, so the migration wipes all rows on first run under the new schema. A `schema_version` integer column is added to detect this.

### 6. Extractor Prompt Design

Each category gets specific query-style instructions in the system prompt:

- **code**: Implementation tech names, library names, algorithms. e.g. `"pytorch transformer implementation"`, `"self-attention github"`
- **academic**: Paper-title style, include survey/review/analysis. e.g. `"attention mechanism survey"`, `"transformer architecture review 2023"`
- **discussion**: Opinion/debate framing. e.g. `"should I use transformer or RNN"`, `"attention mechanism tradeoffs"`
- **product**: App/service/product framing. e.g. `"AI writing assistant app"`, `"transformer based productivity tool"`
- **news**: Recent developments, announcements. e.g. `"transformer AI breakthrough"`, `"LLM regulation policy news"`

---

## Data Flow

```
User input text
    │
    ├──► cache lookup (key = hash(input_text))
    │         hit → return cached items, skip API calls
    │         miss ↓
    ▼
extract_concepts() ──Claude──► query_bundles {code:[...], academic:[...], ...}
    │
    ▼
analyzer.py: for each category in query_bundles, route to CATEGORY_SOURCES
    │
    ├── github.search(code_queries)                      parallel per query
    ├── arxiv.search(academic_queries)                   parallel per query
    ├── semantic_scholar.search(academic_queries)        parallel per query
    ├── hackernews.search(discussion_queries)            parallel per query
    ├── reddit.search(discussion_queries, domain_type)   sequential per query, parallel subreddits
    ├── product_hunt.search(product_queries)             parallel per query
    ├── itunes.search(product_queries)                   parallel per query
    ├── google_play.search(product_queries)              parallel per query
    ├── gdelt.search(news_queries)                       sequential+delay inside gdelt.py, own timeout in analyzer
    └── serper.search(news_queries)                      parallel per query
    │
    ▼
cache.set(input_text, fresh_items)
    │
    ▼
deduplicate → embed → UMAP → graph → report
```

---

## Files to Modify

| File | Change |
|---|---|
| `backend/extractor.py` | New system prompt generating `query_bundles` + keeping `search_queries`; parse and validate; fallback synthetic bundle |
| `backend/analyzer.py` | Remove `USE_*` flags; `CATEGORY_SOURCES` routing; pass `input_text` to cache; separate GDELT timeout; updated `PROD_LIMITS` |
| `backend/cache.py` | `get_cached(input_text: str)`, `set_cache(input_text: str, ...)`; schema_version migration on startup |
| `backend/sources/github.py` | Remove `queries[:3]` cap; parallel per-query fetch + dedup |
| `backend/sources/hackernews.py` | Parallel per-query fetch + dedup |
| `backend/sources/reddit.py` | Sequential per-query, parallel subreddits per query; `domain_type` kwarg preserved; dedup |
| `backend/sources/arxiv.py` | Parallel per-query fetch + dedup |
| `backend/sources/semantic_scholar.py` | Parallel per-query fetch + dedup |
| `backend/sources/product_hunt.py` | Parallel per-query fetch + dedup |
| `backend/sources/itunes.py` | Parallel per-query fetch + dedup |
| `backend/sources/google_play.py` | Parallel per-query fetch + dedup |
| `backend/sources/gdelt.py` | Sequential per-query with 10s delay inside `search()`; own timeout applied in analyzer |
| `backend/sources/serper.py` | Parallel per-query fetch + dedup |

---

## Error Handling

- If Claude omits a category from `query_bundles`, that category's sources are skipped silently.
- If Claude omits `query_bundles` entirely, fall back to synthetic bundle using `search_queries`.
- If a source's parallel queries partially fail, successful results are still used.
- Sources with partial failures yield `count: N` (not 0) in progress events if any queries succeeded.

---

## Out of Scope

- UI changes to display which queries were used per source
- Per-source query count tuning UI
- Query deduplication across bundles (same term in multiple categories is fine)
