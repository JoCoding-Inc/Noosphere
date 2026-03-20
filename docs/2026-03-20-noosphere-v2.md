# Noosphere v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a product validation simulator where users paste a service description and receive a multi-platform social simulation with structured report and PDF export.

**Architecture:** Free-form text input → `context_builder.py` extracts concept nodes → `social_runner.py` runs multi-platform persona simulation via SSE → `generate_report` returns structured JSON → ResultPage dashboard with PDF download. No graph UI; knowledge graph is fully internal.

**Tech Stack:** Python 3.11+, FastAPI, SQLite, Anthropic Claude API, React 18, TypeScript, Vite, Typst (PDF), httpx (HN/Reddit/GitHub fetch), uv (package manager)

---

## File Map

```
noosphere/                          ← new project root
├── backend/
│   ├── __init__.py
│   ├── main.py                     ← FastAPI app, SSE, job management (NEW)
│   ├── db.py                       ← SQLite helpers (NEW)
│   ├── context_builder.py          ← text → context nodes (NEW)
│   ├── exporter.py                 ← Typst PDF export (NEW, adapted from legacy)
│   └── simulation/                 ← copied from legacy, some files modified
│       ├── __init__.py
│       ├── models.py               ← copied as-is
│       ├── agent.py                ← copied as-is
│       ├── graph_utils.py          ← copied as-is
│       ├── rate_limiter.py         ← copied as-is
│       ├── persona_generator.py    ← copied as-is (no changes needed)
│       ├── social_rounds.py        ← MODIFIED: generate_report → JSON output
│       ├── social_runner.py        ← MODIFIED: new signature (input_text + context_nodes)
│       └── platforms/              ← copied as-is
│           ├── __init__.py
│           ├── base.py
│           ├── hackernews.py
│           ├── indiehackers.py
│           ├── linkedin.py
│           ├── producthunt.py
│           └── reddit_startups.py
├── frontend/
│   ├── index.html
│   ├── package.json
│   ├── vite.config.ts
│   ├── tsconfig.json
│   └── src/
│       ├── main.tsx
│       ├── App.tsx                 ← routing (NEW)
│       ├── types.ts                ← shared TypeScript types (NEW)
│       ├── api.ts                  ← API helpers (NEW)
│       ├── hooks/
│       │   └── useSimulation.ts    ← SSE hook (adapted from legacy)
│       ├── components/
│       │   ├── Header.tsx          ← adapted from legacy
│       │   ├── SocialFeedView.tsx  ← NEW
│       │   ├── PersonaCardView.tsx ← NEW
│       │   └── ReportView.tsx      ← NEW
│       └── pages/
│           ├── HomePage.tsx        ← NEW
│           ├── SimulatePage.tsx    ← NEW (adapted)
│           ├── ResultPage.tsx      ← NEW
│           └── HistoryPage.tsx     ← NEW
├── tests/
│   ├── test_context_builder.py
│   ├── test_db.py
│   └── test_social_runner.py
├── .env.example
├── pyproject.toml
└── docker-compose.yml
```

---

## Task 1: Project Scaffolding

**Files:**
- Create: `noosphere/` (new folder at `/Users/taeyoungpark/Desktop/noosphere-v2/`)
- Rename: `/Desktop/noosphere` → `/Desktop/noosphere-legacy`

> **Note:** The new project lives at `/Users/taeyoungpark/Desktop/noosphere-v2` during development. After legacy rename, it moves to `/Users/taeyoungpark/Desktop/noosphere`.

- [ ] **Step 1: Rename legacy project**

```bash
mv /Users/taeyoungpark/Desktop/noosphere /Users/taeyoungpark/Desktop/noosphere-legacy
```

- [ ] **Step 2: Create new project folder and init git**

```bash
mkdir -p /Users/taeyoungpark/Desktop/noosphere
cd /Users/taeyoungpark/Desktop/noosphere
git init
```

- [ ] **Step 3: Create pyproject.toml**

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "noosphere"
version = "2.0.0"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.111",
    "uvicorn[standard]>=0.29",
    "httpx>=0.27",
    "anthropic>=0.28",
    "python-dotenv>=1.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"

[tool.setuptools.packages.find]
where = ["."]
```

- [ ] **Step 4: Create .env.example**

```bash
cat > .env.example << 'EOF'
ANTHROPIC_API_KEY=your_api_key_here
# Optional: HN/Reddit/GitHub context enrichment (leave empty to skip)
CONTEXT_ENRICH=true
EOF
```

- [ ] **Step 5: Copy simulation engine from legacy**

```bash
mkdir -p /Users/taeyoungpark/Desktop/noosphere/backend
touch /Users/taeyoungpark/Desktop/noosphere/backend/__init__.py
cp -r /Users/taeyoungpark/Desktop/noosphere-legacy/backend/simulation \
      /Users/taeyoungpark/Desktop/noosphere/backend/simulation
```

- [ ] **Step 6: Create test directory**

```bash
mkdir -p /Users/taeyoungpark/Desktop/noosphere/tests
touch /Users/taeyoungpark/Desktop/noosphere/tests/__init__.py
```

- [ ] **Step 7: Install dependencies**

```bash
cd /Users/taeyoungpark/Desktop/noosphere
uv venv && uv pip install -e ".[dev]"
```

- [ ] **Step 8: Commit scaffold**

```bash
cd /Users/taeyoungpark/Desktop/noosphere
git add .
git commit -m "chore: scaffold noosphere v2 with simulation engine"
```

---

## Task 2: Database Layer

**Files:**
- Create: `backend/db.py`
- Create: `tests/test_db.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_db.py
import pytest
import tempfile
import os
from backend.db import init_db, create_simulation, update_simulation_status, \
    save_sim_results, get_sim_results, list_history, get_simulation

@pytest.fixture
def db_path(tmp_path):
    path = str(tmp_path / "test.db")
    init_db(path)
    return path

def test_create_and_get_simulation(db_path):
    sim_id = "test-sim-id-001"
    create_simulation(db_path, sim_id, "My SaaS app", "English",
                      {"num_rounds": 5}, "saas")
    row = get_simulation(db_path, sim_id)
    assert row["input_text"] == "My SaaS app"
    assert row["status"] == "running"

def test_update_status(db_path):
    sim_id = "test-sim-id-002"
    create_simulation(db_path, sim_id, "test", "English", {}, "tech")
    update_simulation_status(db_path, sim_id, "completed")
    row = get_simulation(db_path, sim_id)
    assert row["status"] == "completed"

def test_save_and_get_results(db_path):
    sim_id = "test-sim-id-003"
    create_simulation(db_path, sim_id, "test", "English", {}, "tech")
    save_sim_results(db_path, sim_id,
                     posts={"hackernews": []},
                     personas={"hackernews": []},
                     report_json={"verdict": "positive"},
                     report_md="## Report")
    result = get_sim_results(db_path, sim_id)
    assert result["report_json"]["verdict"] == "positive"

def test_list_history(db_path):
    create_simulation(db_path, "id-a", "App one", "English", {}, "saas")
    create_simulation(db_path, "id-b", "App two", "Korean", {}, "fintech")
    rows = list_history(db_path)
    assert len(rows) == 2
    assert rows[0]["input_text_snippet"] is not None
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd /Users/taeyoungpark/Desktop/noosphere
uv run pytest tests/test_db.py -v
```

Expected: ImportError or ModuleNotFoundError

- [ ] **Step 3: Implement db.py**

```python
# backend/db.py
from __future__ import annotations
import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "noosphere.db"


def _conn(path: str | Path = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db(path: str | Path = DB_PATH) -> None:
    with _conn(path) as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS simulations (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                input_text TEXT NOT NULL,
                language TEXT NOT NULL DEFAULT 'English',
                config_json TEXT NOT NULL DEFAULT '{}',
                status TEXT NOT NULL DEFAULT 'running',
                domain TEXT NOT NULL DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS sim_results (
                sim_id TEXT PRIMARY KEY,
                posts_json TEXT NOT NULL DEFAULT '{}',
                personas_json TEXT NOT NULL DEFAULT '{}',
                report_json TEXT NOT NULL DEFAULT '{}',
                report_md TEXT NOT NULL DEFAULT ''
            );
        """)


def create_simulation(
    path: str | Path,
    sim_id: str,
    input_text: str,
    language: str,
    config: dict,
    domain: str,
) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with _conn(path) as conn:
        conn.execute(
            "INSERT INTO simulations VALUES (?,?,?,?,?,?,?)",
            (sim_id, now, input_text, language, json.dumps(config), "running", domain),
        )


def update_simulation_status(path: str | Path, sim_id: str, status: str) -> None:
    with _conn(path) as conn:
        conn.execute(
            "UPDATE simulations SET status=? WHERE id=?", (status, sim_id)
        )


def get_simulation(path: str | Path, sim_id: str) -> dict | None:
    with _conn(path) as conn:
        row = conn.execute(
            "SELECT * FROM simulations WHERE id=?", (sim_id,)
        ).fetchone()
    return dict(row) if row else None


def save_sim_results(
    path: str | Path,
    sim_id: str,
    posts: dict,
    personas: dict,
    report_json: dict,
    report_md: str,
) -> None:
    with _conn(path) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO sim_results VALUES (?,?,?,?,?)",
            (sim_id, json.dumps(posts), json.dumps(personas),
             json.dumps(report_json), report_md),
        )


def get_sim_results(path: str | Path, sim_id: str) -> dict | None:
    with _conn(path) as conn:
        row = conn.execute(
            "SELECT * FROM sim_results WHERE sim_id=?", (sim_id,)
        ).fetchone()
    if not row:
        return None
    d = dict(row)
    d["posts_json"] = json.loads(d["posts_json"])
    d["personas_json"] = json.loads(d["personas_json"])
    d["report_json"] = json.loads(d["report_json"])
    return d


def list_history(path: str | Path = DB_PATH, limit: int = 50) -> list[dict]:
    with _conn(path) as conn:
        rows = conn.execute(
            """SELECT id, created_at, input_text, language, config_json, status, domain
               FROM simulations ORDER BY created_at DESC LIMIT ?""",
            (limit,),
        ).fetchall()
    result = []
    for row in rows:
        d = dict(row)
        d["input_text_snippet"] = d["input_text"][:60]
        d["config"] = json.loads(d.pop("config_json"))
        result.append(d)
    return result
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/test_db.py -v
```

Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/db.py tests/test_db.py
git commit -m "feat: add SQLite database layer"
```

---

## Task 3: Context Builder

**Files:**
- Create: `backend/context_builder.py`
- Create: `tests/test_context_builder.py`

Context builder parses input text with Claude to extract concept nodes. Optionally fetches related HN posts. Returns `list[dict]` matching the context node schema.

- [ ] **Step 1: Write failing tests**

```python
# tests/test_context_builder.py
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from backend.context_builder import extract_concepts_from_text, build_context_nodes


@pytest.mark.asyncio
async def test_extract_concepts_returns_list():
    """extract_concepts_from_text returns list of concept dicts."""
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text='["task management", "SaaS", "productivity"]')]

    with patch("backend.context_builder._get_client") as mock_get_client:
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)
        mock_get_client.return_value = mock_client

        result = await extract_concepts_from_text("A SaaS app for task management")
        assert isinstance(result, list)
        assert len(result) > 0


@pytest.mark.asyncio
async def test_build_context_nodes_from_text_only():
    """build_context_nodes returns valid node dicts even without external fetch."""
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text='["task management", "productivity"]')]

    with patch("backend.context_builder._get_client") as mock_get_client:
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)
        mock_get_client.return_value = mock_client

        nodes = await build_context_nodes(
            "A SaaS app for task management",
            enrich=False,
        )
        assert len(nodes) >= 1
        for node in nodes:
            assert "id" in node
            assert "title" in node
            assert "source" in node
            assert "abstract" in node
            assert node["source"] == "input_text"
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
uv run pytest tests/test_context_builder.py -v
```

Expected: ImportError

- [ ] **Step 3: Implement context_builder.py**

```python
# backend/context_builder.py
from __future__ import annotations
import json
import logging
import os
import re
import uuid

import anthropic
import httpx

logger = logging.getLogger(__name__)

_client: anthropic.AsyncAnthropic | None = None


def _get_client() -> anthropic.AsyncAnthropic:
    global _client
    if _client is None:
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY not set")
        _client = anthropic.AsyncAnthropic(api_key=api_key, timeout=30.0)
    return _client


async def extract_concepts_from_text(text: str) -> list[str]:
    """Use Claude to extract key concepts/entities from product description."""
    prompt = (
        f"Extract 5-10 key concepts, technologies, or market categories from this "
        f"product description. Return ONLY a JSON array of strings.\n\n{text[:2000]}"
    )
    client = _get_client()
    msg = await client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = msg.content[0].text.strip()
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.DOTALL).strip()
    try:
        concepts = json.loads(raw)
        return [str(c) for c in concepts if c][:10]
    except json.JSONDecodeError:
        # Fallback: split on newlines or commas
        return [c.strip(' "') for c in re.split(r"[,\n]", raw) if c.strip(' "')][:10]


async def _fetch_hn_posts(query: str, limit: int = 5) -> list[dict]:
    """Fetch related HN posts for a concept query."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                "https://hn.algolia.com/api/v1/search",
                params={"query": query, "tags": "story", "hitsPerPage": limit},
            )
            resp.raise_for_status()
            hits = resp.json().get("hits", [])
            return [
                {
                    "id": str(uuid.uuid4()),
                    "title": h.get("title", query)[:200],
                    "source": "hackernews",
                    "abstract": (h.get("story_text") or h.get("title", ""))[:300],
                }
                for h in hits
                if h.get("title")
            ]
    except Exception as exc:
        logger.warning("HN fetch failed for %r: %s", query, exc)
        return []


def _nodes_from_concepts(text: str, concepts: list[str]) -> list[dict]:
    """Create context nodes from extracted concepts using the input text as abstract source."""
    text_snippet = text[:300].replace("\n", " ")
    nodes = []
    for concept in concepts:
        nodes.append({
            "id": str(uuid.uuid4()),
            "title": concept,
            "source": "input_text",
            "abstract": f"{concept} — extracted from: {text_snippet}",
        })
    return nodes


async def build_context_nodes(
    input_text: str,
    enrich: bool = True,
    max_nodes: int = 30,
) -> list[dict]:
    """
    Main entry point. Returns list of context node dicts for the simulation engine.

    Args:
        input_text: Raw product/service description from user
        enrich: If True, fetch related HN posts to augment context
        max_nodes: Cap on total nodes returned
    """
    concepts = await extract_concepts_from_text(input_text)
    nodes = _nodes_from_concepts(input_text, concepts)

    if enrich and concepts:
        # Fetch HN posts for top 3 concepts in parallel
        import asyncio
        tasks = [_fetch_hn_posts(c, limit=3) for c in concepts[:3]]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for r in results:
            if isinstance(r, list):
                nodes.extend(r)

    # Deduplicate by title
    seen_titles: set[str] = set()
    deduped = []
    for n in nodes:
        t = n["title"].lower()
        if t not in seen_titles:
            seen_titles.add(t)
            deduped.append(n)

    return deduped[:max_nodes]


async def detect_domain(input_text: str) -> str:
    """Detect the product domain (e.g. 'SaaS', 'fintech', 'developer tools')."""
    prompt = (
        f"In 2-4 words, what is the domain of this product? "
        f"Examples: 'developer tools', 'B2B SaaS', 'fintech', 'consumer app'.\n\n"
        f"Reply with only the domain string.\n\n{input_text[:500]}"
    )
    client = _get_client()
    try:
        msg = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=32,
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text.strip()[:50]
    except Exception:
        return "technology"
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/test_context_builder.py -v
```

Expected: Both tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/context_builder.py tests/test_context_builder.py
git commit -m "feat: add context_builder for text-to-nodes extraction"
```

---

## Task 4: Modify social_runner.py

**Files:**
- Modify: `backend/simulation/social_runner.py`
- Create: `tests/test_social_runner.py`

Change signature from `nodes: list[dict]` to `input_text: str, context_nodes: list[dict]`.
Also collect personas during the run so they can be saved to DB.

- [ ] **Step 1: Write failing tests**

```python
# tests/test_social_runner.py
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

FAKE_NODES = [
    {"id": "n1", "title": "SaaS", "source": "input_text", "abstract": "Software as a Service"},
    {"id": "n2", "title": "productivity", "source": "input_text", "abstract": "task management"},
]

@pytest.mark.asyncio
async def test_run_simulation_yields_sim_start():
    """run_simulation with context_nodes emits sim_start event."""
    from backend.simulation.social_runner import run_simulation

    events = []
    async for event in run_simulation(
        input_text="A SaaS app",
        context_nodes=FAKE_NODES,
        domain="saas",
        max_agents=2,
        num_rounds=1,
        platforms=["hackernews"],
        language="English",
    ):
        events.append(event)
        if event["type"] in ("sim_done", "sim_error"):
            break

    types = [e["type"] for e in events]
    assert "sim_start" in types


@pytest.mark.asyncio
async def test_run_simulation_empty_nodes_yields_error():
    """run_simulation with empty context_nodes yields sim_error."""
    from backend.simulation.social_runner import run_simulation

    events = []
    async for event in run_simulation(
        input_text="A SaaS app",
        context_nodes=[],
        domain="saas",
    ):
        events.append(event)

    assert events[0]["type"] == "sim_error"
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
uv run pytest tests/test_social_runner.py -v
```

Expected: TypeError (wrong arguments) or ImportError

- [ ] **Step 3: Verify variable names in social_runner.py**

Before editing, confirm that `run_simulation` uses `nodes` and `idea_text` as variable names in its body:

```bash
grep -n "nodes\|idea_text" backend/simulation/social_runner.py | head -20
```

Expected: multiple lines using `nodes` and `idea_text`. If different names are used, replace accordingly in Step 4.

- [ ] **Step 4: Update social_runner.py signature**

In `backend/simulation/social_runner.py`, change the `run_simulation` function signature and early guard:

```python
async def run_simulation(
    input_text: str,           # ← was: nodes: list[dict]
    context_nodes: list[dict], # ← new parameter
    domain: str,
    max_agents: int = 50,
    num_rounds: int = 12,
    platforms: list[str] | None = None,
    language: str = "English",
    edges: list[dict] | None = None,
    activation_rate: float = 0.25,
) -> AsyncGenerator[dict, None]:
    nodes = context_nodes  # alias for rest of function body (no other changes needed)
    idea_text = input_text  # alias for rest of function body
    if not nodes:
        yield {"type": "sim_error", "message": "No context nodes to simulate"}
        yield {"type": "sim_done"}
        return
    # ... rest of the function body is unchanged ...
```

Also update the `sim_report` event to include `personas` for DB persistence:

In the final `yield {"type": "sim_report", ...}` block, add personas:
```python
yield {
    "type": "sim_report",
    "data": {
        "markdown": report_md,
        "platform_states": { ... },  # existing
        "personas": {
            name: [
                {"node_id": p.node_id, "name": p.name, "role": p.role,
                 "mbti": p.mbti, "bias": p.bias, "interests": p.interests}
                for p in personas_list
            ]
            for name, personas_list in platform_personas.items()
        },
    },
}
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/test_social_runner.py -v
```

Expected: Both tests PASS (note: test_run_simulation_yields_sim_start may be slow — it makes real API calls if ANTHROPIC_API_KEY is set; mock it if needed for CI)

- [ ] **Step 5: Commit**

```bash
git add backend/simulation/social_runner.py tests/test_social_runner.py
git commit -m "feat: update social_runner to accept input_text + context_nodes"
```

---

## Task 5: Structured Report Generation

**Files:**
- Modify: `backend/simulation/social_rounds.py` (only `generate_report` function)

Replace free-form markdown output with structured JSON + markdown rendering.

- [ ] **Step 1: Locate generate_report in social_rounds.py**

The function is at lines 325-376. Replace it entirely.

- [ ] **Step 2: Replace generate_report**

```python
# backend/simulation/social_rounds.py — replace generate_report function

_REPORT_SYSTEM = """\
You are an expert product analyst synthesizing a multi-platform social simulation.
You must respond with ONLY valid JSON matching the schema exactly."""

_REPORT_SCHEMA = """\
{
  "verdict": "positive" | "mixed" | "skeptical" | "negative",
  "evidence_count": <integer: total posts + comments across all platforms>,
  "segments": [
    {
      "name": "developer" | "investor" | "early_adopter" | "skeptic" | "pm",
      "sentiment": "positive" | "neutral" | "negative",
      "summary": "<2-3 sentence summary of this segment's reaction>",
      "key_quotes": ["<quote 1>", "<quote 2>"]
    }
  ],
  "criticism_clusters": [
    {
      "theme": "<short theme label, e.g. 'pricing concerns'>",
      "count": <integer: how many personas raised this>,
      "examples": ["<example quote 1>", "<example quote 2>"]
    }
  ],
  "improvements": [
    {
      "suggestion": "<concrete improvement suggestion>",
      "frequency": <integer: how many personas implied this>
    }
  ]
}"""


async def generate_report(
    platform_states: list[PlatformState],
    idea_text: str,
    domain: str,
    language: str = "English",
) -> tuple[dict, str]:
    """Returns (report_json, report_md)."""
    platform_summaries = []
    total_evidence = 0
    for state in platform_states:
        posts = state.posts
        total_evidence += len(posts)
        top_posts = sorted(
            [p for p in posts if p.parent_id is None],
            key=lambda p: -p.upvotes
        )[:5]
        top_text = "\n".join(
            f"  [{p.upvotes}↑] {p.author_name} ({p.action_type}): {p.content[:200]}"
            for p in top_posts
        )
        platform_summaries.append(
            f"### {state.platform_name}\n"
            f"Posts: {len([p for p in posts if p.parent_id is None])}, "
            f"Comments: {len([p for p in posts if p.parent_id is not None])}\n"
            f"Top content:\n{top_text}"
        )

    prompt = (
        f"Domain: {domain}\n"
        f"Product: {idea_text[:400]}\n\n"
        f"Simulation results across platforms:\n\n"
        + "\n\n".join(platform_summaries)
        + f"\n\nAnalyze this simulation and return a JSON report matching this schema:\n{_REPORT_SCHEMA}\n\n"
        f"Instructions:\n"
        f"- verdict: overall market reception\n"
        f"- segments: include all 5 segment types even if some have neutral sentiment\n"
        f"- criticism_clusters: top 3-5 recurring objections\n"
        f"- improvements: top 3-5 actionable suggestions\n"
        f"- All text fields must be in {language}\n"
        f"Return ONLY the JSON, no markdown wrapper."
    )

    client = _get_client()
    report_json: dict = {}
    for model in ("claude-sonnet-4-6", "claude-opus-4-6"):
        try:
            msg = await client.messages.create(
                model=model,
                max_tokens=8192,
                system=_REPORT_SYSTEM,
                messages=[{"role": "user", "content": prompt}],
                timeout=300.0,
            )
            raw = msg.content[0].text.strip()
            raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.DOTALL).strip()
            report_json = json.loads(raw)
            break
        except Exception as exc:
            logger.warning("Report model %s failed: %s", model, exc)

    if not report_json:
        report_json = {
            "verdict": "mixed",
            "evidence_count": total_evidence,
            "segments": [],
            "criticism_clusters": [],
            "improvements": [],
        }

    report_md = _render_report_md(report_json, idea_text, language)
    return report_json, report_md


def _render_report_md(report: dict, idea_text: str, language: str) -> str:
    verdict_emoji = {
        "positive": "✅", "mixed": "⚖️", "skeptical": "🤔", "negative": "❌"
    }.get(report.get("verdict", "mixed"), "⚖️")

    lines = [
        f"# Product Validation Report",
        f"",
        f"## {verdict_emoji} Overall Verdict: {report.get('verdict', 'N/A').title()}",
        f"*Based on {report.get('evidence_count', 0)} simulated interactions*",
        f"",
        f"## Segment Reactions",
    ]
    for seg in report.get("segments", []):
        sentiment_icon = {"positive": "👍", "neutral": "😐", "negative": "👎"}.get(
            seg.get("sentiment", "neutral"), "😐"
        )
        lines.append(f"### {sentiment_icon} {seg.get('name', '').replace('_', ' ').title()}")
        lines.append(seg.get("summary", ""))
        for q in seg.get("key_quotes", []):
            lines.append(f'> "{q}"')
        lines.append("")

    lines += ["## Criticism Patterns"]
    for cluster in report.get("criticism_clusters", []):
        lines.append(f"### {cluster.get('theme', '')} ({cluster.get('count', 0)} mentions)")
        for ex in cluster.get("examples", [])[:2]:
            lines.append(f'- "{ex}"')
        lines.append("")

    lines += ["## Improvement Suggestions"]
    for imp in report.get("improvements", []):
        lines.append(f"- **{imp.get('suggestion', '')}** *(mentioned {imp.get('frequency', 1)}x)*")

    return "\n".join(lines)
```

Also add `import json, re` at top of social_rounds.py if not already present.

Update the call site in `social_runner.py` — `generate_report` now returns a tuple `(report_json, report_md)`:

```python
# In social_runner.py, replace:
report_md = await generate_report(...)
# With:
report_json, report_md = await generate_report(...)
```

And update the `sim_report` event to include both:
```python
yield {
    "type": "sim_report",
    "data": {
        "report_json": report_json,
        "markdown": report_md,
        "platform_states": { ... },
        "personas": { ... },
    },
}
```

- [ ] **Step 3: Verify imports in social_rounds.py include json and re**

Check the top of `social_rounds.py` and add if missing:
```python
import json
import re
```

- [ ] **Step 4: Run existing tests to confirm nothing is broken**

```bash
uv run pytest tests/ -v
```

- [ ] **Step 5: Commit**

```bash
git add backend/simulation/social_rounds.py backend/simulation/social_runner.py
git commit -m "feat: generate_report returns structured JSON + markdown"
```

---

## Task 6: FastAPI Backend (main.py)

**Files:**
- Create: `backend/main.py`
- Create: `.env` from `.env.example`

- [ ] **Step 1: Create .env**

```bash
cp .env.example .env
# Edit .env and set your ANTHROPIC_API_KEY
```

- [ ] **Step 2: Create main.py**

```python
# backend/main.py
from __future__ import annotations
import asyncio
import json
import logging
import os
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, field_validator

from backend.db import (
    init_db, create_simulation, update_simulation_status,
    save_sim_results, get_sim_results, list_history, get_simulation, DB_PATH
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MAX_JOBS = int(os.getenv("MAX_JOBS", "5"))
_sim_jobs: dict[str, dict] = {}  # sim_id → {"queue": asyncio.Queue, "created_at": float}
_sim_jobs_lock = asyncio.Lock()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db(DB_PATH)
    yield


app = FastAPI(title="Noosphere v2", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class SimConfig(BaseModel):
    input_text: str
    language: str = "English"
    num_rounds: int = 12
    max_agents: int = 50
    platforms: list[str] = ["hackernews", "producthunt", "indiehackers", "reddit_startups", "linkedin"]
    activation_rate: float = 0.25

    @field_validator("input_text")
    @classmethod
    def text_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("input_text must not be empty")
        return v.strip()

    @field_validator("activation_rate")
    @classmethod
    def rate_valid(cls, v: float) -> float:
        if not (0.1 <= v <= 1.0):
            raise ValueError("activation_rate must be between 0.1 and 1.0")
        return v

    @field_validator("num_rounds")
    @classmethod
    def rounds_valid(cls, v: int) -> int:
        return max(1, min(v, 30))

    @field_validator("max_agents")
    @classmethod
    def agents_valid(cls, v: int) -> int:
        return max(1, min(v, 150))


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/simulate")
async def simulate(config: SimConfig):
    """Start a simulation. Returns sim_id for streaming."""
    async with _sim_jobs_lock:
        running = sum(1 for j in _sim_jobs.values()
                      if time.time() - j["created_at"] < 1800)
        if running >= MAX_JOBS:
            raise HTTPException(429, "Too many concurrent simulations")

    sim_id = str(uuid.uuid4())
    domain = ""  # will be detected during run
    create_simulation(DB_PATH, sim_id, config.input_text, config.language,
                      config.dict(), domain)

    queue: asyncio.Queue[dict | None] = asyncio.Queue()
    async with _sim_jobs_lock:
        _sim_jobs[sim_id] = {"queue": queue, "created_at": time.time()}

    async def run():
        from backend.context_builder import build_context_nodes, detect_domain
        from backend.simulation.social_runner import run_simulation

        try:
            queue.put_nowait({"type": "sim_progress", "message": "Building context..."})
            enrich = os.getenv("CONTEXT_ENRICH", "true").lower() == "true"
            context_nodes = await build_context_nodes(config.input_text, enrich=enrich)
            domain_str = await detect_domain(config.input_text)

            queue.put_nowait({"type": "sim_progress",
                              "message": f"Domain: {domain_str}. Starting simulation..."})

            posts_by_platform: dict = {}
            personas_by_platform: dict = {}
            report_json: dict = {}
            report_md: str = ""

            async for event in run_simulation(
                input_text=config.input_text,
                context_nodes=context_nodes,
                domain=domain_str,
                max_agents=config.max_agents,
                num_rounds=config.num_rounds,
                platforms=config.platforms,
                language=config.language,
                activation_rate=config.activation_rate,
            ):
                if event["type"] == "sim_report":
                    data = event["data"]
                    posts_by_platform = data.get("platform_states", {})
                    personas_by_platform = data.get("personas", {})
                    report_json = data.get("report_json", {})
                    report_md = data.get("markdown", "")
                queue.put_nowait(event)

            save_sim_results(DB_PATH, sim_id, posts_by_platform,
                             personas_by_platform, report_json, report_md)
            update_simulation_status(DB_PATH, sim_id, "completed")

        except Exception as exc:
            logger.error("Simulation %s failed: %s", sim_id, exc)
            queue.put_nowait({"type": "sim_error", "message": str(exc)})
            update_simulation_status(DB_PATH, sim_id, "failed")
        finally:
            queue.put_nowait({"type": "sim_done"})
            queue.put_nowait(None)  # sentinel

    asyncio.create_task(run())
    return {"sim_id": sim_id}


@app.get("/simulate-stream/{sim_id}")
async def simulate_stream(sim_id: str):
    """SSE stream for a simulation job."""
    async with _sim_jobs_lock:
        job = _sim_jobs.get(sim_id)

    if not job:
        # Check DB — maybe already completed
        sim = get_simulation(DB_PATH, sim_id)
        if not sim:
            raise HTTPException(404, "Simulation not found")

    queue = job["queue"] if job else None

    async def event_generator():
        if queue is None:
            # Completed, stream results from DB
            results = get_sim_results(DB_PATH, sim_id)
            if results:
                yield f"data: {json.dumps({'type': 'sim_report', 'data': results})}\n\n"
            yield f"data: {json.dumps({'type': 'sim_done'})}\n\n"
            return

        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=60.0)
            except asyncio.TimeoutError:
                yield "data: {\"type\": \"heartbeat\"}\n\n"
                continue
            if event is None:
                break
            yield f"data: {json.dumps(event)}\n\n"
            if event.get("type") == "sim_done":
                break

        async with _sim_jobs_lock:
            _sim_jobs.pop(sim_id, None)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/results/{sim_id}")
async def get_results(sim_id: str):
    results = get_sim_results(DB_PATH, sim_id)
    if not results:
        raise HTTPException(404, "Results not found")
    return results


@app.get("/history")
async def history():
    return list_history(DB_PATH)


@app.get("/export/{sim_id}")
async def export_pdf(sim_id: str):
    """Generate and return PDF report."""
    results = get_sim_results(DB_PATH, sim_id)
    if not results:
        raise HTTPException(404, "Results not found")
    sim = get_simulation(DB_PATH, sim_id)

    from backend.exporter import build_pdf
    pdf_bytes = await build_pdf(
        report_md=results["report_md"],
        input_text=sim["input_text"] if sim else "",
        sim_id=sim_id,
    )
    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="noosphere-report-{sim_id[:8]}.pdf"'},
    )
```

- [ ] **Step 3: Smoke test the server starts**

```bash
uv run uvicorn backend.main:app --port 8000 --reload
# In another terminal:
curl http://localhost:8000/health
```

Expected: `{"status": "ok"}`

- [ ] **Step 4: Commit**

```bash
git add backend/main.py
git commit -m "feat: add FastAPI backend with SSE streaming and job management"
```

---

## Task 7: PDF Exporter

**Files:**
- Create: `backend/exporter.py`

Adapts the legacy Typst-based approach. If `typst` is not installed, falls back to plain-text PDF via `fpdf2`.

- [ ] **Step 1: Install fpdf2 as fallback**

Add to `pyproject.toml` dependencies:
```toml
"fpdf2>=2.7",
```

```bash
uv pip install fpdf2
```

- [ ] **Step 2: Create exporter.py**

```python
# backend/exporter.py
from __future__ import annotations
import asyncio
import logging
import shutil
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)


async def build_pdf(report_md: str, input_text: str, sim_id: str) -> bytes:
    """Build PDF from report markdown. Uses typst if available, else fpdf2 fallback."""
    if shutil.which("typst"):
        return await _build_with_typst(report_md, input_text, sim_id)
    return _build_with_fpdf(report_md, input_text)


async def _build_with_typst(report_md: str, input_text: str, sim_id: str) -> bytes:
    typst_src = _md_to_typst(report_md, input_text)
    with tempfile.TemporaryDirectory() as tmpdir:
        src_path = Path(tmpdir) / "report.typ"
        out_path = Path(tmpdir) / "report.pdf"
        src_path.write_text(typst_src, encoding="utf-8")
        proc = await asyncio.create_subprocess_exec(
            "typst", "compile", str(src_path), str(out_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await asyncio.wait_for(proc.communicate(), timeout=30.0)
        if proc.returncode != 0:
            logger.error("typst failed: %s", stderr.decode())
            return _build_with_fpdf(report_md, input_text)
        return out_path.read_bytes()


def _md_to_typst(report_md: str, input_text: str) -> str:
    escaped = report_md.replace("\\", "\\\\").replace('"', '\\"')
    snippet = input_text[:200].replace('"', '\\"')
    return f"""
#set page(margin: 2cm)
#set text(font: "Liberation Serif", size: 11pt)

#align(center)[
  #text(size: 18pt, weight: "bold")[Noosphere — Product Validation Report]
  #v(0.5em)
  #text(size: 10pt, fill: gray)[{snippet}...]
]
#v(1em)
#line(length: 100%)
#v(1em)

#{_md_blocks_to_typst(report_md)}
"""


def _md_blocks_to_typst(md: str) -> str:
    lines = []
    for line in md.splitlines():
        if line.startswith("# "):
            lines.append(f'= {line[2:]}')
        elif line.startswith("## "):
            lines.append(f'== {line[3:]}')
        elif line.startswith("### "):
            lines.append(f'=== {line[4:]}')
        elif line.startswith("> "):
            lines.append(f'#quote[{line[2:]}]')
        elif line.startswith("- "):
            lines.append(f'- {line[2:]}')
        else:
            lines.append(line)
    return "\n".join(lines)


def _build_with_fpdf(report_md: str, input_text: str) -> bytes:
    from fpdf import FPDF
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=11)
    pdf.set_title("Noosphere Product Validation Report")

    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "Noosphere — Product Validation Report", ln=True, align="C")
    pdf.set_font("Helvetica", size=9)
    pdf.cell(0, 6, input_text[:100] + "...", ln=True, align="C")
    pdf.ln(4)

    for line in report_md.splitlines():
        if line.startswith("# "):
            pdf.set_font("Helvetica", "B", 14)
            pdf.cell(0, 8, line[2:], ln=True)
        elif line.startswith("## "):
            pdf.set_font("Helvetica", "B", 12)
            pdf.cell(0, 7, line[3:], ln=True)
        elif line.startswith("### "):
            pdf.set_font("Helvetica", "B", 11)
            pdf.cell(0, 6, line[4:], ln=True)
        elif line.startswith("> "):
            pdf.set_font("Helvetica", "I", 10)
            pdf.multi_cell(0, 5, f'  "{line[2:]}"')
        elif line.strip():
            pdf.set_font("Helvetica", size=10)
            pdf.multi_cell(0, 5, line)
        else:
            pdf.ln(2)

    return pdf.output()
```

- [ ] **Step 3: Verify export endpoint works**

```bash
# Start server, run a simulation, then:
curl http://localhost:8000/export/<sim_id> -o test.pdf
# Should produce a PDF file
```

- [ ] **Step 4: Commit**

```bash
git add backend/exporter.py pyproject.toml
git commit -m "feat: add PDF exporter with typst + fpdf2 fallback"
```

---

## Task 8: Frontend Scaffolding

**Files:**
- Create: `frontend/` directory with Vite + React + TypeScript

- [ ] **Step 1: Scaffold with Vite**

```bash
cd /Users/taeyoungpark/Desktop/noosphere
npm create vite@latest frontend -- --template react-ts
cd frontend && npm install
npm install react-router-dom
```

- [ ] **Step 2: Create shared types file**

```typescript
// frontend/src/types.ts
export interface SimConfig {
  input_text: string
  language: string
  num_rounds: number
  max_agents: number
  platforms: string[]
  activation_rate: number
}

export interface SocialPost {
  id: string
  platform: string
  author_node_id: string
  author_name: string
  content: string
  action_type: string
  round_num: number
  upvotes: number
  downvotes: number
  parent_id: string | null
}

export interface Persona {
  node_id: string
  name: string
  role: string
  mbti: string
  bias: string
  interests: string[]
}

export interface ReportSegment {
  name: string
  sentiment: 'positive' | 'neutral' | 'negative'
  summary: string
  key_quotes: string[]
}

export interface CriticismCluster {
  theme: string
  count: number
  examples: string[]
}

export interface Improvement {
  suggestion: string
  frequency: number
}

export interface ReportJSON {
  verdict: 'positive' | 'mixed' | 'skeptical' | 'negative'
  evidence_count: number
  segments: ReportSegment[]
  criticism_clusters: CriticismCluster[]
  improvements: Improvement[]
}

export interface SimResults {
  sim_id: string
  posts_json: Record<string, SocialPost[]>
  personas_json: Record<string, Persona[]>
  report_json: ReportJSON
  report_md: string
}

export interface HistoryItem {
  id: string
  created_at: string
  input_text_snippet: string
  language: string
  config: SimConfig
  status: 'running' | 'completed' | 'failed'
  domain: string
}
```

- [ ] **Step 3: Create api.ts**

```typescript
// frontend/src/api.ts
const API_BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

export async function startSimulation(config: import('./types').SimConfig): Promise<{ sim_id: string }> {
  const res = await fetch(`${API_BASE}/simulate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(config),
  })
  if (!res.ok) throw new Error(`Failed to start simulation: ${res.status}`)
  return res.json()
}

export function streamSimulation(sim_id: string): EventSource {
  return new EventSource(`${API_BASE}/simulate-stream/${sim_id}`)
}

export async function getResults(sim_id: string): Promise<import('./types').SimResults> {
  const res = await fetch(`${API_BASE}/results/${sim_id}`)
  if (!res.ok) throw new Error(`Failed to get results: ${res.status}`)
  return res.json()
}

export async function getHistory(): Promise<import('./types').HistoryItem[]> {
  const res = await fetch(`${API_BASE}/history`)
  if (!res.ok) throw new Error('Failed to get history')
  return res.json()
}

export function exportPdfUrl(sim_id: string): string {
  return `${API_BASE}/export/${sim_id}`
}
```

- [ ] **Step 4: Set up App.tsx with routing**

```tsx
// frontend/src/App.tsx
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { HomePage } from './pages/HomePage'
import { SimulatePage } from './pages/SimulatePage'
import { ResultPage } from './pages/ResultPage'
import { HistoryPage } from './pages/HistoryPage'

export function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/simulate/:simId" element={<SimulatePage />} />
        <Route path="/result/:simId" element={<ResultPage />} />
        <Route path="/history" element={<HistoryPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
```

- [ ] **Step 5: Update main.tsx**

```tsx
// frontend/src/main.tsx
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { App } from './App'
import './index.css'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>
)
```

- [ ] **Step 6: Verify dev server starts**

```bash
cd frontend && npm run dev
```

Expected: Vite dev server running at http://localhost:5173

- [ ] **Step 7: Commit**

```bash
cd ..
git add frontend/
git commit -m "feat: scaffold frontend with React + TypeScript + routing"
```

---

## Task 9: HomePage

**Files:**
- Create: `frontend/src/pages/HomePage.tsx`
- Create: `frontend/src/components/Header.tsx`

- [ ] **Step 1: Create Header component**

```tsx
// frontend/src/components/Header.tsx
import { Link } from 'react-router-dom'

export function Header() {
  return (
    <header style={{
      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      padding: '12px 24px', borderBottom: '1px solid #e2e8f0',
      background: '#fff',
    }}>
      <Link to="/" style={{ textDecoration: 'none', color: 'inherit' }}>
        <span style={{ fontWeight: 700, fontSize: 18, letterSpacing: '-0.03em' }}>
          noosphere
        </span>
      </Link>
      <nav style={{ display: 'flex', gap: 16 }}>
        <Link to="/history" style={{ color: '#64748b', fontSize: 14, textDecoration: 'none' }}>
          History
        </Link>
      </nav>
    </header>
  )
}
```

- [ ] **Step 2: Create HomePage**

```tsx
// frontend/src/pages/HomePage.tsx
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Header } from '../components/Header'
import { startSimulation } from '../api'
import type { SimConfig } from '../types'

const PLATFORM_OPTIONS = [
  { id: 'hackernews', label: 'Hacker News' },
  { id: 'producthunt', label: 'Product Hunt' },
  { id: 'indiehackers', label: 'Indie Hackers' },
  { id: 'reddit_startups', label: 'Reddit r/startups' },
  { id: 'linkedin', label: 'LinkedIn' },
]

const LANGUAGE_OPTIONS = ['English', '한국어', '日本語', 'Español', 'Français', 'Deutsch']

const DEFAULT_CONFIG: Omit<SimConfig, 'input_text'> = {
  language: 'English',
  num_rounds: 12,
  max_agents: 50,
  platforms: ['hackernews', 'producthunt', 'indiehackers', 'reddit_startups', 'linkedin'],
  activation_rate: 0.25,
}

export function HomePage() {
  const navigate = useNavigate()
  const [inputText, setInputText] = useState('')
  const [config, setConfig] = useState(DEFAULT_CONFIG)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const togglePlatform = (id: string) => {
    setConfig(c => ({
      ...c,
      platforms: c.platforms.includes(id)
        ? c.platforms.filter(p => p !== id)
        : [...c.platforms, id],
    }))
  }

  const handleRun = async () => {
    if (!inputText.trim()) {
      setError('Please enter a product description.')
      return
    }
    if (config.platforms.length === 0) {
      setError('Please select at least one platform.')
      return
    }
    setError('')
    setLoading(true)
    try {
      const { sim_id } = await startSimulation({ input_text: inputText, ...config })
      navigate(`/simulate/${sim_id}`)
    } catch (e: any) {
      setError(e.message)
      setLoading(false)
    }
  }

  return (
    <div style={{ minHeight: '100vh', background: '#fafafa' }}>
      <Header />
      <main style={{ maxWidth: 720, margin: '0 auto', padding: '48px 24px' }}>
        <h1 style={{ fontSize: 32, fontWeight: 700, marginBottom: 8, letterSpacing: '-0.04em' }}>
          How will the market react?
        </h1>
        <p style={{ color: '#64748b', marginBottom: 32 }}>
          Paste your product description and simulate reactions across HN, Product Hunt, LinkedIn and more.
        </p>

        <textarea
          value={inputText}
          onChange={e => setInputText(e.target.value)}
          placeholder="Paste your landing page copy, pitch deck text, or product description here..."
          rows={10}
          style={{
            width: '100%', padding: 16, fontSize: 15, border: '1px solid #e2e8f0',
            borderRadius: 8, resize: 'vertical', fontFamily: 'inherit',
            boxSizing: 'border-box', background: '#fff',
          }}
        />

        <details style={{ marginTop: 16 }}>
          <summary style={{ cursor: 'pointer', color: '#64748b', fontSize: 14, marginBottom: 12 }}>
            Options
          </summary>

          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, marginBottom: 16 }}>
            <label style={{ fontSize: 14 }}>
              Language&nbsp;
              <select value={config.language}
                onChange={e => setConfig(c => ({ ...c, language: e.target.value }))}>
                {LANGUAGE_OPTIONS.map(l => <option key={l}>{l}</option>)}
              </select>
            </label>
            <label style={{ fontSize: 14 }}>
              Rounds&nbsp;
              <input type="number" min={1} max={30} value={config.num_rounds}
                onChange={e => setConfig(c => ({ ...c, num_rounds: +e.target.value }))}
                style={{ width: 60 }} />
            </label>
            <label style={{ fontSize: 14 }}>
              Agents&nbsp;
              <input type="number" min={5} max={150} value={config.max_agents}
                onChange={e => setConfig(c => ({ ...c, max_agents: +e.target.value }))}
                style={{ width: 60 }} />
            </label>
            <label style={{ fontSize: 14 }}>
              Activation&nbsp;
              <input type="range" min={0.1} max={1.0} step={0.05}
                value={config.activation_rate}
                onChange={e => setConfig(c => ({ ...c, activation_rate: +e.target.value }))} />
              &nbsp;{Math.round(config.activation_rate * 100)}%
            </label>
          </div>

          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            {PLATFORM_OPTIONS.map(p => (
              <button key={p.id}
                onClick={() => togglePlatform(p.id)}
                style={{
                  padding: '6px 14px', fontSize: 13, borderRadius: 20, cursor: 'pointer',
                  border: '1px solid', transition: 'all 0.15s',
                  background: config.platforms.includes(p.id) ? '#1e293b' : '#fff',
                  color: config.platforms.includes(p.id) ? '#fff' : '#64748b',
                  borderColor: config.platforms.includes(p.id) ? '#1e293b' : '#e2e8f0',
                }}>
                {p.label}
              </button>
            ))}
          </div>
        </details>

        {error && (
          <p style={{ color: '#ef4444', fontSize: 14, marginTop: 12 }}>{error}</p>
        )}

        <button
          onClick={handleRun}
          disabled={loading}
          style={{
            marginTop: 24, padding: '14px 32px', fontSize: 16, fontWeight: 600,
            background: loading ? '#94a3b8' : '#1e293b', color: '#fff',
            border: 'none', borderRadius: 8, cursor: loading ? 'not-allowed' : 'pointer',
          }}>
          {loading ? 'Starting...' : 'Run Simulation →'}
        </button>
      </main>
    </div>
  )
}
```

- [ ] **Step 3: Verify page renders**

```bash
cd frontend && npm run dev
# Open http://localhost:5173 — should show input form
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/HomePage.tsx frontend/src/components/Header.tsx
git commit -m "feat: add HomePage with simulation config form"
```

---

## Task 10: SimulatePage (SSE Streaming)

**Files:**
- Create: `frontend/src/pages/SimulatePage.tsx`
- Create: `frontend/src/hooks/useSimulation.ts`

- [ ] **Step 1: Create useSimulation hook**

```typescript
// frontend/src/hooks/useSimulation.ts
import { useEffect, useRef, useState } from 'react'
import type { SocialPost } from '../types'

export type SimEvent =
  | { type: 'sim_start'; agent_count: number }
  | { type: 'sim_progress'; message: string }
  | { type: 'sim_persona'; name: string; role: string; platform: string }
  | { type: 'sim_platform_post'; platform: string; post: SocialPost }
  | { type: 'sim_round_summary'; round_num: number }
  | { type: 'sim_report'; data: any }
  | { type: 'sim_warning'; message: string }
  | { type: 'sim_error'; message: string }
  | { type: 'sim_done' }

interface SimState {
  status: 'connecting' | 'running' | 'done' | 'error'
  events: SimEvent[]
  postsByPlatform: Record<string, SocialPost[]>
  report: any | null
  personas: any | null
  errorMsg: string
  roundNum: number
  agentCount: number
}

export function useSimulation(simId: string): SimState {
  const [state, setState] = useState<SimState>({
    status: 'connecting',
    events: [],
    postsByPlatform: {},
    report: null,
    personas: null,
    errorMsg: '',
    roundNum: 0,
    agentCount: 0,
  })
  const esRef = useRef<EventSource | null>(null)

  useEffect(() => {
    if (!simId) return
    const API_BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'
    const es = new EventSource(`${API_BASE}/simulate-stream/${simId}`)
    esRef.current = es

    es.onmessage = (e) => {
      const event: SimEvent = JSON.parse(e.data)
      setState(prev => {
        const next = { ...prev, events: [...prev.events, event] }
        if (event.type === 'sim_start') {
          next.status = 'running'
          next.agentCount = event.agent_count
        } else if (event.type === 'sim_platform_post') {
          const posts = { ...prev.postsByPlatform }
          posts[event.platform] = [...(posts[event.platform] || []), event.post]
          next.postsByPlatform = posts
        } else if (event.type === 'sim_round_summary') {
          next.roundNum = event.round_num
        } else if (event.type === 'sim_report') {
          next.report = event.data.report_json
          next.personas = event.data.personas
        } else if (event.type === 'sim_error') {
          next.status = 'error'
          next.errorMsg = event.message
        } else if (event.type === 'sim_done') {
          next.status = 'done'
          es.close()
        }
        return next
      })
    }

    es.onerror = () => {
      setState(prev => ({ ...prev, status: 'error', errorMsg: 'Connection lost' }))
      es.close()
    }

    return () => es.close()
  }, [simId])

  return state
}
```

- [ ] **Step 2: Create SimulatePage**

```tsx
// frontend/src/pages/SimulatePage.tsx
import { useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Header } from '../components/Header'
import { useSimulation } from '../hooks/useSimulation'

const PLATFORM_LABELS: Record<string, string> = {
  hackernews: 'Hacker News',
  producthunt: 'Product Hunt',
  indiehackers: 'Indie Hackers',
  reddit_startups: 'Reddit r/startups',
  linkedin: 'LinkedIn',
}

export function SimulatePage() {
  const { simId } = useParams<{ simId: string }>()
  const navigate = useNavigate()
  const sim = useSimulation(simId!)

  useEffect(() => {
    if (sim.status === 'done' && simId) {
      navigate(`/result/${simId}`)
    }
  }, [sim.status, simId, navigate])

  const progressMessages = sim.events
    .filter(e => e.type === 'sim_progress')
    .map(e => (e as any).message)

  const recentPosts = Object.values(sim.postsByPlatform)
    .flat()
    .slice(-10)
    .reverse()

  return (
    <div style={{ minHeight: '100vh', background: '#fafafa' }}>
      <Header />
      <main style={{ maxWidth: 720, margin: '0 auto', padding: '48px 24px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 24 }}>
          {sim.status !== 'error' && (
            <span style={{
              display: 'inline-block', width: 10, height: 10, borderRadius: '50%',
              background: '#22c55e',
              animation: 'pulse 1.5s infinite',
            }} />
          )}
          <h2 style={{ margin: 0, fontSize: 20, fontWeight: 600 }}>
            {sim.status === 'connecting' ? 'Connecting...' :
             sim.status === 'error' ? 'Simulation failed' :
             `Round ${sim.roundNum} — ${sim.agentCount} agents`}
          </h2>
        </div>

        {sim.status === 'error' && (
          <p style={{ color: '#ef4444' }}>{sim.errorMsg}</p>
        )}

        {progressMessages.length > 0 && (
          <p style={{ color: '#64748b', fontSize: 14, marginBottom: 16 }}>
            {progressMessages[progressMessages.length - 1]}
          </p>
        )}

        <div style={{ borderTop: '1px solid #e2e8f0', paddingTop: 16 }}>
          {recentPosts.map(post => (
            <div key={post.id} style={{
              padding: '10px 0', borderBottom: '1px solid #f1f5f9',
            }}>
              <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 4 }}>
                <span style={{
                  fontSize: 11, padding: '2px 8px', borderRadius: 10,
                  background: '#f1f5f9', color: '#64748b',
                }}>
                  {PLATFORM_LABELS[post.platform] || post.platform}
                </span>
                <span style={{ fontWeight: 600, fontSize: 13 }}>{post.author_name}</span>
                <span style={{ fontSize: 11, color: '#94a3b8' }}>{post.action_type}</span>
              </div>
              <p style={{ margin: 0, fontSize: 14, color: '#1e293b' }}>{post.content}</p>
            </div>
          ))}
        </div>
      </main>
    </div>
  )
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/SimulatePage.tsx frontend/src/hooks/useSimulation.ts
git commit -m "feat: add SimulatePage with SSE streaming and live feed"
```

---

## Task 11: ResultPage Components

**Files:**
- Create: `frontend/src/components/SocialFeedView.tsx`
- Create: `frontend/src/components/PersonaCardView.tsx`
- Create: `frontend/src/components/ReportView.tsx`
- Create: `frontend/src/pages/ResultPage.tsx`

- [ ] **Step 1: Create SocialFeedView**

```tsx
// frontend/src/components/SocialFeedView.tsx
import { useState } from 'react'
import type { SocialPost } from '../types'

const PLATFORM_ORDER = ['hackernews', 'producthunt', 'indiehackers', 'reddit_startups', 'linkedin']
const PLATFORM_LABELS: Record<string, string> = {
  hackernews: 'Hacker News',
  producthunt: 'Product Hunt',
  indiehackers: 'Indie Hackers',
  reddit_startups: 'Reddit',
  linkedin: 'LinkedIn',
}

function PostCard({ post, depth = 0 }: { post: SocialPost; depth?: number }) {
  return (
    <div style={{
      marginLeft: depth * 20,
      borderLeft: depth > 0 ? '2px solid #e2e8f0' : 'none',
      paddingLeft: depth > 0 ? 12 : 0,
      paddingBottom: 8,
    }}>
      <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 4 }}>
        <span style={{ fontWeight: 600, fontSize: 13 }}>{post.author_name}</span>
        <span style={{
          fontSize: 10, padding: '1px 6px', borderRadius: 8,
          background: '#f1f5f9', color: '#94a3b8', textTransform: 'uppercase',
        }}>{post.action_type}</span>
        {post.upvotes > 0 && (
          <span style={{ fontSize: 11, color: '#64748b' }}>▲ {post.upvotes}</span>
        )}
      </div>
      <p style={{ margin: 0, fontSize: 14, color: '#1e293b', lineHeight: 1.5 }}>
        {post.content}
      </p>
    </div>
  )
}

export function SocialFeedView({ posts }: { posts: Record<string, SocialPost[]> }) {
  const platforms = PLATFORM_ORDER.filter(p => posts[p]?.length)
  const [active, setActive] = useState(platforms[0] || '')

  return (
    <div>
      <div style={{ display: 'flex', gap: 4, marginBottom: 16, borderBottom: '1px solid #e2e8f0' }}>
        {platforms.map(p => (
          <button key={p} onClick={() => setActive(p)}
            style={{
              padding: '8px 16px', fontSize: 13, cursor: 'pointer', border: 'none',
              background: 'none', fontWeight: active === p ? 600 : 400,
              borderBottom: active === p ? '2px solid #1e293b' : '2px solid transparent',
              color: active === p ? '#1e293b' : '#64748b',
            }}>
            {PLATFORM_LABELS[p]} ({posts[p].length})
          </button>
        ))}
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        {(posts[active] || []).map(post => (
          <PostCard key={post.id} post={post}
            depth={post.parent_id ? 1 : 0} />
        ))}
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Create PersonaCardView**

```tsx
// frontend/src/components/PersonaCardView.tsx
import type { Persona } from '../types'

const PLATFORM_LABELS: Record<string, string> = {
  hackernews: 'HN',
  producthunt: 'PH',
  indiehackers: 'IH',
  reddit_startups: 'Reddit',
  linkedin: 'LinkedIn',
}

const BIAS_COLORS: Record<string, string> = {
  academic: '#6366f1',
  commercial: '#22c55e',
  skeptic: '#f59e0b',
  evangelist: '#ec4899',
}

export function PersonaCardView({ personas }: { personas: Record<string, Persona[]> }) {
  const allPersonas = Object.entries(personas).flatMap(([platform, list]) =>
    list.map(p => ({ ...p, platform }))
  )

  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))',
      gap: 12,
    }}>
      {allPersonas.slice(0, 24).map((p, i) => (
        <div key={i} style={{
          padding: 14, borderRadius: 8, border: '1px solid #e2e8f0',
          background: '#fff',
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
            <span style={{ fontWeight: 600, fontSize: 14 }}>{p.name}</span>
            <span style={{ fontSize: 11, color: '#94a3b8' }}>
              {PLATFORM_LABELS[p.platform] || p.platform}
            </span>
          </div>
          <p style={{ margin: '0 0 6px', fontSize: 12, color: '#64748b' }}>{p.role}</p>
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
            <span style={{
              fontSize: 10, padding: '2px 7px', borderRadius: 10,
              background: BIAS_COLORS[p.bias] || '#e2e8f0', color: '#fff',
            }}>{p.bias}</span>
            <span style={{
              fontSize: 10, padding: '2px 7px', borderRadius: 10,
              background: '#f1f5f9', color: '#64748b',
            }}>{p.mbti}</span>
          </div>
        </div>
      ))}
    </div>
  )
}
```

- [ ] **Step 3: Create ReportView**

```tsx
// frontend/src/components/ReportView.tsx
import type { ReportJSON } from '../types'

const VERDICT_CONFIG = {
  positive: { emoji: '✅', color: '#22c55e', label: 'Positive' },
  mixed: { emoji: '⚖️', color: '#f59e0b', label: 'Mixed' },
  skeptical: { emoji: '🤔', color: '#f97316', label: 'Skeptical' },
  negative: { emoji: '❌', color: '#ef4444', label: 'Negative' },
}

const SENTIMENT_ICONS = { positive: '👍', neutral: '😐', negative: '👎' }

export function ReportView({ report, simId }: { report: ReportJSON; simId: string }) {
  const API_BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'
  const v = VERDICT_CONFIG[report.verdict] || VERDICT_CONFIG.mixed

  return (
    <div>
      {/* Verdict */}
      <div style={{
        padding: 20, borderRadius: 10, marginBottom: 24,
        border: `1px solid ${v.color}20`,
        background: `${v.color}08`,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 4 }}>
          <span style={{ fontSize: 24 }}>{v.emoji}</span>
          <span style={{ fontSize: 20, fontWeight: 700, color: v.color }}>{v.label}</span>
        </div>
        <p style={{ margin: 0, fontSize: 14, color: '#64748b' }}>
          Based on {report.evidence_count} simulated interactions
        </p>
      </div>

      {/* Segment Reactions */}
      <h3 style={{ fontSize: 16, fontWeight: 600, marginBottom: 12 }}>Segment Reactions</h3>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12, marginBottom: 24 }}>
        {report.segments.map(seg => (
          <div key={seg.name} style={{
            padding: 14, borderRadius: 8, border: '1px solid #e2e8f0', background: '#fff',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
              <span>{SENTIMENT_ICONS[seg.sentiment]}</span>
              <span style={{ fontWeight: 600, fontSize: 14 }}>
                {seg.name.replace('_', ' ').replace(/\b\w/g, c => c.toUpperCase())}
              </span>
            </div>
            <p style={{ margin: '0 0 8px', fontSize: 14, color: '#475569' }}>{seg.summary}</p>
            {seg.key_quotes.map((q, i) => (
              <p key={i} style={{
                margin: '4px 0', paddingLeft: 12, borderLeft: '3px solid #e2e8f0',
                fontSize: 13, color: '#64748b', fontStyle: 'italic',
              }}>"{q}"</p>
            ))}
          </div>
        ))}
      </div>

      {/* Criticism Clusters */}
      <h3 style={{ fontSize: 16, fontWeight: 600, marginBottom: 12 }}>Criticism Patterns</h3>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 24 }}>
        {report.criticism_clusters.map((c, i) => (
          <div key={i} style={{
            padding: 12, borderRadius: 8, border: '1px solid #fecdd3',
            background: '#fff1f2',
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
              <span style={{ fontWeight: 600, fontSize: 14 }}>{c.theme}</span>
              <span style={{ fontSize: 12, color: '#94a3b8' }}>{c.count} mentions</span>
            </div>
            {c.examples.slice(0, 2).map((ex, j) => (
              <p key={j} style={{ margin: '2px 0', fontSize: 13, color: '#64748b' }}>
                — "{ex}"
              </p>
            ))}
          </div>
        ))}
      </div>

      {/* Improvements */}
      <h3 style={{ fontSize: 16, fontWeight: 600, marginBottom: 12 }}>Improvement Suggestions</h3>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginBottom: 32 }}>
        {report.improvements.map((imp, i) => (
          <div key={i} style={{
            display: 'flex', justifyContent: 'space-between', alignItems: 'center',
            padding: '10px 14px', borderRadius: 8, border: '1px solid #d1fae5',
            background: '#f0fdf4',
          }}>
            <span style={{ fontSize: 14, color: '#1e293b' }}>{imp.suggestion}</span>
            <span style={{ fontSize: 12, color: '#94a3b8', whiteSpace: 'nowrap', marginLeft: 8 }}>
              ×{imp.frequency}
            </span>
          </div>
        ))}
      </div>

      {/* PDF Download */}
      <a
        href={`${API_BASE}/export/${simId}`}
        download
        style={{
          display: 'inline-block', padding: '12px 24px', background: '#1e293b',
          color: '#fff', borderRadius: 8, textDecoration: 'none', fontSize: 14,
          fontWeight: 600,
        }}>
        ↓ Download PDF Report
      </a>
    </div>
  )
}
```

- [ ] **Step 4: Create ResultPage**

```tsx
// frontend/src/pages/ResultPage.tsx
import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Header } from '../components/Header'
import { SocialFeedView } from '../components/SocialFeedView'
import { PersonaCardView } from '../components/PersonaCardView'
import { ReportView } from '../components/ReportView'
import { getResults } from '../api'
import type { SimResults } from '../types'

type Tab = 'report' | 'feed' | 'personas'

export function ResultPage() {
  const { simId } = useParams<{ simId: string }>()
  const navigate = useNavigate()
  const [results, setResults] = useState<SimResults | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [tab, setTab] = useState<Tab>('report')

  useEffect(() => {
    if (!simId) return
    getResults(simId)
      .then(setResults)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [simId])

  const tabs: { id: Tab; label: string }[] = [
    { id: 'report', label: 'Report' },
    { id: 'feed', label: 'Social Feed' },
    { id: 'personas', label: 'Personas' },
  ]

  return (
    <div style={{ minHeight: '100vh', background: '#fafafa' }}>
      <Header />
      <main style={{ maxWidth: 900, margin: '0 auto', padding: '32px 24px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
          <button onClick={() => navigate('/')}
            style={{ background: 'none', border: 'none', color: '#64748b', cursor: 'pointer', fontSize: 14 }}>
            ← New simulation
          </button>
        </div>

        {loading && <p style={{ color: '#64748b' }}>Loading results...</p>}
        {error && <p style={{ color: '#ef4444' }}>{error}</p>}

        {results && (
          <>
            <div style={{ display: 'flex', gap: 4, marginBottom: 24, borderBottom: '1px solid #e2e8f0' }}>
              {tabs.map(t => (
                <button key={t.id} onClick={() => setTab(t.id)}
                  style={{
                    padding: '10px 20px', fontSize: 14, cursor: 'pointer', border: 'none',
                    background: 'none', fontWeight: tab === t.id ? 600 : 400,
                    borderBottom: tab === t.id ? '2px solid #1e293b' : '2px solid transparent',
                    color: tab === t.id ? '#1e293b' : '#64748b',
                  }}>
                  {t.label}
                </button>
              ))}
            </div>

            {tab === 'report' && (
              <ReportView report={results.report_json} simId={simId!} />
            )}
            {tab === 'feed' && (
              <SocialFeedView posts={results.posts_json} />
            )}
            {tab === 'personas' && (
              <PersonaCardView personas={results.personas_json} />
            )}
          </>
        )}
      </main>
    </div>
  )
}
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/ frontend/src/pages/ResultPage.tsx
git commit -m "feat: add ResultPage with social feed, persona cards, and report view"
```

---

## Task 12: HistoryPage

**Files:**
- Create: `frontend/src/pages/HistoryPage.tsx`

- [ ] **Step 1: Create HistoryPage**

```tsx
// frontend/src/pages/HistoryPage.tsx
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Header } from '../components/Header'
import { getHistory } from '../api'
import type { HistoryItem } from '../types'

const STATUS_CONFIG = {
  completed: { color: '#22c55e', label: 'Done' },
  running: { color: '#f59e0b', label: 'Running' },
  failed: { color: '#ef4444', label: 'Failed' },
}

export function HistoryPage() {
  const navigate = useNavigate()
  const [items, setItems] = useState<HistoryItem[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    getHistory()
      .then(setItems)
      .finally(() => setLoading(false))
  }, [])

  return (
    <div style={{ minHeight: '100vh', background: '#fafafa' }}>
      <Header />
      <main style={{ maxWidth: 800, margin: '0 auto', padding: '32px 24px' }}>
        <h1 style={{ fontSize: 24, fontWeight: 700, marginBottom: 24 }}>Simulation History</h1>

        {loading && <p style={{ color: '#64748b' }}>Loading...</p>}
        {!loading && items.length === 0 && (
          <p style={{ color: '#64748b' }}>No simulations yet. <a href="/">Run one →</a></p>
        )}

        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {items.map(item => {
            const status = STATUS_CONFIG[item.status] || STATUS_CONFIG.failed
            const date = new Date(item.created_at).toLocaleDateString()
            const platforms = item.config?.platforms?.join(', ') || ''

            return (
              <div
                key={item.id}
                onClick={() => item.status === 'completed' && navigate(`/result/${item.id}`)}
                style={{
                  padding: 16, borderRadius: 8, border: '1px solid #e2e8f0',
                  background: '#fff', cursor: item.status === 'completed' ? 'pointer' : 'default',
                  transition: 'border-color 0.15s',
                }}
                onMouseEnter={e => {
                  if (item.status === 'completed')
                    (e.currentTarget as HTMLDivElement).style.borderColor = '#1e293b'
                }}
                onMouseLeave={e => {
                  (e.currentTarget as HTMLDivElement).style.borderColor = '#e2e8f0'
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                  <p style={{ margin: 0, fontSize: 15, fontWeight: 500, color: '#1e293b', flex: 1 }}>
                    {item.input_text_snippet}…
                  </p>
                  <span style={{
                    fontSize: 11, padding: '2px 8px', borderRadius: 10,
                    background: `${status.color}20`, color: status.color,
                    marginLeft: 12, whiteSpace: 'nowrap',
                  }}>{status.label}</span>
                </div>
                <div style={{ display: 'flex', gap: 16, marginTop: 8, fontSize: 12, color: '#94a3b8' }}>
                  <span>{date}</span>
                  <span>{item.language}</span>
                  {item.domain && <span>{item.domain}</span>}
                </div>
              </div>
            )
          })}
        </div>
      </main>
    </div>
  )
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/pages/HistoryPage.tsx
git commit -m "feat: add HistoryPage with simulation list"
```

---

## Task 13: Integration & Docker

**Files:**
- Create: `docker-compose.yml`
- Create: `frontend/.env` (for VITE_API_URL)

- [ ] **Step 1: Create docker-compose.yml**

```yaml
# docker-compose.yml
services:
  backend:
    build: .
    ports:
      - "8000:8000"
    env_file: .env
    volumes:
      - ./noosphere.db:/app/noosphere.db

  frontend:
    image: node:20-alpine
    working_dir: /app
    volumes:
      - ./frontend:/app
    ports:
      - "5173:5173"
    command: sh -c "npm install && npm run dev -- --host"
    environment:
      # Mac/Windows: host.docker.internal; Linux: host-gateway
      - VITE_API_URL=http://host.docker.internal:8000
```

- [ ] **Step 2: Create Dockerfile**

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY pyproject.toml .
RUN pip install uv && uv pip install --system -e .
COPY backend/ backend/
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 3: End-to-end smoke test**

```bash
# Terminal 1: start backend
cd /Users/taeyoungpark/Desktop/noosphere
uv run uvicorn backend.main:app --port 8000 --reload

# Terminal 2: start frontend
cd frontend && npm run dev

# Open http://localhost:5173
# 1. Paste a product description
# 2. Click "Run Simulation"
# 3. Watch SSE stream on SimulatePage
# 4. Verify redirect to ResultPage with report + feed + personas
# 5. Click History in header — verify entry appears
# 6. Click PDF download — verify file downloads
```

- [ ] **Step 4: Final commit**

```bash
cd /Users/taeyoungpark/Desktop/noosphere
git add .
git commit -m "feat: complete noosphere v2 — product validation simulator"
```

---

## Verification Checklist

Before declaring done, verify:

- [ ] `POST /simulate` returns `sim_id`
- [ ] SSE stream at `/simulate-stream/{sim_id}` emits `sim_start`, `sim_platform_post`, `sim_report`, `sim_done`
- [ ] `GET /results/{sim_id}` returns report_json with all 4 sections
- [ ] `GET /history` returns list with correct fields
- [ ] `GET /export/{sim_id}` returns a valid PDF
- [ ] Frontend: HomePage form submits and navigates to SimulatePage
- [ ] Frontend: SimulatePage shows live posts and redirects on completion
- [ ] Frontend: ResultPage shows all 3 tabs (Report, Social Feed, Personas)
- [ ] Frontend: HistoryPage lists past simulations and navigates to results
- [ ] All pytest tests pass: `uv run pytest tests/ -v`
