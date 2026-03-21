# Simulation Checkpoint & Resume Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Checkpoint simulation state to SQLite after each round, enable worker resume from last checkpoint via a user-initiated button, and auto-reconnect SSE on transient network drops.

**Architecture:** A new `sim_checkpoints` SQLite table stores the full simulation loop state (platform posts, personas, context nodes) after every completed round. On worker crash, the Celery task can be re-dispatched with the same `sim_id`; it reads the checkpoint and skips straight to the next round. The frontend auto-reconnects SSE with exponential backoff and shows a "재개하기" button when a checkpoint is available.

**Tech Stack:** Python (FastAPI, Celery, SQLite, Redis Streams, asyncio), TypeScript (React, EventSource API)

---

## File Map

**Created:**
- `backend/tests/test_checkpoint.py` — DB checkpoint function tests
- `backend/tests/test_social_runner_restore.py` — dataclass restore helper tests

**Modified:**
- `backend/db.py` — add `sim_checkpoints` table + `save_checkpoint`, `get_checkpoint`, `delete_checkpoint`
- `backend/simulation/social_runner.py` — add checkpoint param, restore helpers, yield `sim_checkpoint_data`
- `backend/tasks.py` — intercept `sim_checkpoint_data`, read checkpoint on start, delete on completion
- `backend/main.py` — add `/simulate/{sim_id}/resume`, `/simulate/{sim_id}/status`, `Last-Event-ID` SSE support
- `frontend/src/api.ts` — add `resumeSimulation`, `getSimulationStatus`
- `frontend/src/hooks/useSimulation.ts` — SSE auto-reconnect + `sim_resume` event + `lastRound` state
- `frontend/src/pages/SimulatePage.tsx` — Resume button in error state

---

## Task 1: DB — `sim_checkpoints` table and CRUD functions

**Files:**
- Modify: `backend/db.py`
- Create: `backend/tests/test_checkpoint.py`

- [ ] **Step 1: Write failing tests for checkpoint DB functions**

Create `backend/tests/test_checkpoint.py`:

```python
import json
import pytest
import tempfile
from pathlib import Path
from backend.db import init_db, save_checkpoint, get_checkpoint, delete_checkpoint


@pytest.fixture
def db_path():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = Path(f.name)
    init_db(path)
    yield path
    path.unlink(missing_ok=True)


def test_get_checkpoint_returns_none_when_missing(db_path):
    assert get_checkpoint(db_path, "nonexistent") is None


def test_save_and_get_checkpoint(db_path):
    save_checkpoint(
        db_path,
        sim_id="sim-1",
        last_round=3,
        platform_states={"hackernews": {"platform_name": "hackernews", "round_num": 3, "recent_speakers": {}, "posts": []}},
        personas={"hackernews": [{"node_id": "n1", "name": "Alice", "role": "engineer", "age": 30,
                                   "seniority": "senior", "affiliation": "startup", "company": "Acme",
                                   "mbti": "INTJ", "interests": ["AI"], "skepticism": 5,
                                   "commercial_focus": 5, "innovation_openness": 7, "source_title": "HN post"}]},
        context_nodes=[{"id": "c1", "title": "Test", "source": "input_text", "abstract": "abc"}],
        domain="ai_tools",
        analysis_md="## Analysis",
        ontology={"nodes": []},
        raw_items=[],
    )
    cp = get_checkpoint(db_path, "sim-1")
    assert cp is not None
    assert cp["last_round"] == 3
    assert cp["domain"] == "ai_tools"
    assert cp["platform_states"]["hackernews"]["round_num"] == 3
    assert cp["personas"]["hackernews"][0]["name"] == "Alice"
    assert cp["context_nodes"][0]["id"] == "c1"
    assert cp["ontology"] == {"nodes": []}
    assert cp["raw_items"] == []


def test_save_checkpoint_overwrites_previous(db_path):
    for round_num in [1, 2, 3]:
        save_checkpoint(db_path, "sim-1", round_num, {}, {}, [], "domain", "", None, [])
    cp = get_checkpoint(db_path, "sim-1")
    assert cp["last_round"] == 3


def test_delete_checkpoint(db_path):
    save_checkpoint(db_path, "sim-1", 1, {}, {}, [], "domain", "", None, [])
    delete_checkpoint(db_path, "sim-1")
    assert get_checkpoint(db_path, "sim-1") is None


def test_delete_nonexistent_checkpoint_is_noop(db_path):
    delete_checkpoint(db_path, "nonexistent")  # should not raise


def test_checkpoint_ontology_null(db_path):
    save_checkpoint(db_path, "sim-1", 1, {}, {}, [], "domain", "", None, [])
    cp = get_checkpoint(db_path, "sim-1")
    assert cp["ontology"] is None
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd /Users/taeyoungpark/Desktop/noosphere
python -m pytest backend/tests/test_checkpoint.py -v
```

Expected: `ImportError` or `AttributeError` — `save_checkpoint` doesn't exist yet.

- [ ] **Step 3: Add `sim_checkpoints` table to `init_db()` in `backend/db.py`**

Inside `init_db()`, the `executescript` call currently ends around line 52 with `""")`. Insert the new DDL BEFORE the closing `"""` — right after the `sim_results` CREATE TABLE block. The surrounding context looks like:

```python
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS simulations (
                ...
            );
            CREATE TABLE IF NOT EXISTS sim_results (
                ...
            );
            CREATE TABLE IF NOT EXISTS sim_checkpoints (    # <-- ADD THIS BLOCK
                sim_id TEXT PRIMARY KEY,
                last_round INTEGER NOT NULL,
                platform_states_json TEXT NOT NULL,
                personas_json TEXT NOT NULL,
                context_nodes_json TEXT NOT NULL,
                domain TEXT NOT NULL,
                analysis_md TEXT NOT NULL,
                ontology_json TEXT,
                raw_items_json TEXT NOT NULL,
                saved_at TEXT NOT NULL
            );
        """)                                                # <-- closing triple-quote stays here
```

- [ ] **Step 4: Add the three checkpoint functions to `backend/db.py`**

Add after the `get_sim_results` function:

```python
def save_checkpoint(
    path: str | Path,
    sim_id: str,
    last_round: int,
    platform_states: dict,
    personas: dict,
    context_nodes: list,
    domain: str,
    analysis_md: str,
    ontology: dict | None,
    raw_items: list,
) -> None:
    now = _utc_now_iso()
    with _conn(path) as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO sim_checkpoints
            (sim_id, last_round, platform_states_json, personas_json, context_nodes_json,
             domain, analysis_md, ontology_json, raw_items_json, saved_at)
            VALUES (?,?,?,?,?,?,?,?,?,?)
            """,
            (
                sim_id,
                last_round,
                json.dumps(platform_states, ensure_ascii=False),
                json.dumps(personas, ensure_ascii=False),
                json.dumps(context_nodes, ensure_ascii=False),
                domain,
                analysis_md,
                json.dumps(ontology, ensure_ascii=False) if ontology is not None else None,
                json.dumps(raw_items, ensure_ascii=False),
                now,
            ),
        )


def get_checkpoint(path: str | Path, sim_id: str) -> dict | None:
    with _conn(path) as conn:
        row = conn.execute(
            "SELECT * FROM sim_checkpoints WHERE sim_id=?", (sim_id,)
        ).fetchone()
    if not row:
        return None
    d = dict(row)
    d["platform_states"] = json.loads(d.pop("platform_states_json"))
    d["personas"] = json.loads(d.pop("personas_json"))
    d["context_nodes"] = json.loads(d.pop("context_nodes_json"))
    d["ontology"] = json.loads(d["ontology_json"]) if d.get("ontology_json") else None
    d["raw_items"] = json.loads(d.pop("raw_items_json"))
    d.pop("ontology_json", None)
    return d


def delete_checkpoint(path: str | Path, sim_id: str) -> None:
    with _conn(path) as conn:
        conn.execute("DELETE FROM sim_checkpoints WHERE sim_id=?", (sim_id,))
```

- [ ] **Step 5: Add imports to `backend/db.py`**

Verify `import json` is already at the top (it is — line 4). No new import needed.

Also add `save_checkpoint`, `get_checkpoint`, `delete_checkpoint` to the module — they're already added in Step 4.

- [ ] **Step 6: Run tests — confirm they pass**

```bash
python -m pytest backend/tests/test_checkpoint.py -v
```

Expected: all 6 tests PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/db.py backend/tests/test_checkpoint.py
git commit -m "feat: add sim_checkpoints table and CRUD functions"
```

---

## Task 2: social_runner.py — restore helpers and checkpoint emission

**Files:**
- Modify: `backend/simulation/social_runner.py`
- Create: `backend/tests/test_social_runner_restore.py`

- [ ] **Step 1: Write failing tests for restore helpers**

Create `backend/tests/test_social_runner_restore.py`:

```python
import dataclasses
import pytest
from backend.simulation.models import Persona, PlatformState, SocialPost
from backend.simulation.social_runner import _restore_personas, _restore_platform_states


PERSONA_DICT = {
    "hackernews": [
        {
            "node_id": "n1", "name": "Alice", "role": "engineer", "age": 30,
            "seniority": "senior", "affiliation": "startup", "company": "Acme",
            "mbti": "INTJ", "interests": ["AI", "OSS"], "skepticism": 4,
            "commercial_focus": 3, "innovation_openness": 8, "source_title": "HN post"
        }
    ]
}

POST_DICT = {
    "hackernews": {
        "platform_name": "hackernews",
        "round_num": 2,
        "recent_speakers": {"n1": 1},
        "posts": [
            {
                "id": "p1", "platform": "hackernews", "author_node_id": "n1",
                "author_name": "Alice", "content": "Hello", "action_type": "post",
                "round_num": 0, "upvotes": 5, "downvotes": 0, "parent_id": None,
                "structured_data": {"url": "http://example.com"}
            }
        ]
    }
}


def test_restore_personas_returns_persona_instances(db=None):
    result = _restore_personas(PERSONA_DICT)
    assert "hackernews" in result
    personas = result["hackernews"]
    assert len(personas) == 1
    p = personas[0]
    assert isinstance(p, Persona)
    assert p.name == "Alice"
    assert p.age == 30
    assert p.source_title == "HN post"
    # generation is a property, not stored — but should still work
    assert p.generation == "Millennial"


def test_restore_personas_excludes_generation_from_constructor():
    # Confirm we don't try to pass 'generation' as a kwarg (it's a property)
    # If this test passes, no TypeError was raised
    result = _restore_personas(PERSONA_DICT)
    assert result["hackernews"][0].interests == ["AI", "OSS"]


def test_restore_platform_states_returns_platform_state_instances():
    result = _restore_platform_states(POST_DICT)
    assert "hackernews" in result
    state = result["hackernews"]
    assert isinstance(state, PlatformState)
    assert state.platform_name == "hackernews"
    assert state.round_num == 2
    assert state.recent_speakers == {"n1": 1}


def test_restore_platform_states_restores_posts():
    result = _restore_platform_states(POST_DICT)
    posts = result["hackernews"].posts
    assert len(posts) == 1
    post = posts[0]
    assert isinstance(post, SocialPost)
    assert post.id == "p1"
    assert post.structured_data == {"url": "http://example.com"}
    assert post.parent_id is None


def test_restore_platform_states_empty():
    result = _restore_platform_states({})
    assert result == {}


def test_restore_personas_empty():
    result = _restore_personas({})
    assert result == {}
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
python -m pytest backend/tests/test_social_runner_restore.py -v
```

Expected: `ImportError` — `_restore_personas` and `_restore_platform_states` don't exist yet.

- [ ] **Step 3: Add `SocialPost` to the import in `backend/simulation/social_runner.py`**

The current import at line 7 is:
```python
from backend.simulation.models import Persona, PlatformState
```

Change it to:
```python
from backend.simulation.models import Persona, PlatformState, SocialPost
```

- [ ] **Step 3b: Add restore helpers to `backend/simulation/social_runner.py`**

Add these two private functions near the top of the file, after the `_deduplicate_names` function:

```python
def _restore_personas(personas_dict: dict) -> dict[str, list["Persona"]]:
    """Reconstruct Persona dataclass instances from checkpoint dict."""
    result = {}
    for platform_name, persona_list in personas_dict.items():
        restored = []
        for d in persona_list:
            # 'generation' is a @property — must not be passed to constructor
            restored.append(Persona(
                node_id=d["node_id"],
                name=d["name"],
                role=d["role"],
                age=d["age"],
                seniority=d["seniority"],
                affiliation=d["affiliation"],
                company=d["company"],
                mbti=d["mbti"],
                interests=d["interests"],
                skepticism=d["skepticism"],
                commercial_focus=d["commercial_focus"],
                innovation_openness=d["innovation_openness"],
                source_title=d["source_title"],
            ))
        result[platform_name] = restored
    return result


def _restore_platform_states(states_dict: dict) -> dict[str, "PlatformState"]:
    """Reconstruct PlatformState dataclass instances from checkpoint dict."""
    result = {}
    for platform_name, state_d in states_dict.items():
        posts = [
            SocialPost(
                id=p["id"],
                platform=p["platform"],
                author_node_id=p["author_node_id"],
                author_name=p["author_name"],
                content=p["content"],
                action_type=p["action_type"],
                round_num=p["round_num"],
                upvotes=p.get("upvotes", 0),
                downvotes=p.get("downvotes", 0),
                parent_id=p.get("parent_id"),
                structured_data=p.get("structured_data", {}),
            )
            for p in state_d.get("posts", [])
        ]
        result[platform_name] = PlatformState(
            platform_name=state_d["platform_name"],
            posts=posts,
            round_num=state_d.get("round_num", 0),
            recent_speakers=state_d.get("recent_speakers", {}),
        )
    return result
```

- [ ] **Step 4: Run tests — confirm they pass**

```bash
python -m pytest backend/tests/test_social_runner_restore.py -v
```

Expected: all 6 tests PASS.

- [ ] **Step 5: Add `checkpoint` parameter to `run_simulation()` and emit `sim_checkpoint_data`**

In `backend/simulation/social_runner.py`, modify the `run_simulation` signature:

```python
async def run_simulation(
    input_text: str,
    context_nodes: list[dict],
    domain: str,
    max_agents: int = 50,
    num_rounds: int = 12,
    platforms: list[str] | None = None,
    language: str = "English",
    edges: list[dict] | None = None,
    activation_rate: float = 0.25,
    provider: str = "openai",
    ontology: dict | None = None,
    checkpoint: dict | None = None,
) -> AsyncGenerator[dict, None]:
```

Inside `run_simulation`, after the `active_platforms` check, add resume branching. Replace the persona generation block and seed post block with:

```python
    if checkpoint is not None:
        # --- RESUME PATH ---
        platform_personas = _restore_personas(checkpoint["personas"])
        platform_states = _restore_platform_states(checkpoint["platform_states"])
        start_round = checkpoint["last_round"] + 1
        yield {"type": "sim_resume", "from_round": start_round}
    else:
        # --- NORMAL PATH: persona generation (existing code) ---
        platform_personas = {p.name: [] for p in active_platforms}
        # ... (existing persona generation code, unchanged) ...
        # ... (existing seed post code, unchanged) ...
        start_round = 1
```

Then change the round loop from `range(1, num_rounds + 1)` to `range(start_round, num_rounds + 1)`.

After the `yield {"type": "sim_round_summary", ...}` in the round loop, add the checkpoint emission immediately before it:

```python
        # Emit checkpoint data (intercepted by tasks.py, NOT forwarded to Redis)
        yield {
            "type": "sim_checkpoint_data",
            "round_num": round_num,
            "platform_states": {
                name: dataclasses.asdict(state)
                for name, state in platform_states.items()
            },
            "personas": {
                name: [dataclasses.asdict(p) for p in personas_list]
                for name, personas_list in platform_personas.items()
            },
            "context_nodes": context_nodes,
            "domain": domain,
            "analysis_md": "",  # filled in by tasks.py via event enrichment
            "ontology": ontology,
            "raw_items": [],    # filled in by tasks.py via event enrichment
        }
        yield {
            "type": "sim_round_summary",
            "round_num": round_num,
            "platform_summaries": round_summary_stats,
        }
```

Note: `analysis_md` and `raw_items` are not available inside `social_runner.py`. They will be injected by `tasks.py` before calling `save_checkpoint()` (see Task 3).

- [ ] **Step 6: Verify existing tests still pass**

```bash
python -m pytest backend/tests/ -v
```

Expected: all previously passing tests still PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/simulation/social_runner.py backend/tests/test_social_runner_restore.py
git commit -m "feat: add checkpoint restore helpers and sim_checkpoint_data emission"
```

---

## Task 3: tasks.py — intercept checkpoint event, read checkpoint on start

**Files:**
- Modify: `backend/tasks.py`
- Modify: `backend/db.py` (add imports to task imports)

- [ ] **Step 1: Update imports in `backend/tasks.py`**

Add `save_checkpoint`, `get_checkpoint`, `delete_checkpoint` to the import from `backend.db`:

```python
from backend.db import (
    save_sim_results,
    update_simulation_status,
    DB_PATH,
    mark_simulation_started,
    touch_simulation_heartbeat,
    simulation_cancel_requested,
    save_checkpoint,
    get_checkpoint,
    delete_checkpoint,
)
```

- [ ] **Step 2: Read checkpoint on task start and pass to `run_simulation()`**

After `mark_simulation_started` succeeds, add checkpoint lookup. In `_run()`, after the LLM key check block (around line 108) and before `watcher_task` creation, add:

```python
            # Check for existing checkpoint (resume scenario)
            existing_checkpoint = await asyncio.to_thread(get_checkpoint, DB_PATH, sim_id)
```

Store `analysis_md`, `raw_items`, `ontology` from the checkpoint if present, skipping the analysis phase:

In `_run()`, replace the current flow with a conditional. Wrap the `analyze()` → `detect_domain()` → `generate_analysis_report()` → `build_ontology()` block to be skipped when a checkpoint exists:

```python
            if existing_checkpoint:
                # Resume: restore pre-simulation data from checkpoint
                raw_items = existing_checkpoint["raw_items"]
                domain_str = existing_checkpoint["domain"]
                analysis_md = existing_checkpoint["analysis_md"]
                ontology = existing_checkpoint["ontology"]
                context_nodes = existing_checkpoint["context_nodes"]
                # NOTE: do NOT publish sim_resume here — social_runner.py yields it
                # and tasks.py will forward it to Redis via the normal event loop below
            else:
                # Fresh run: run analysis pipeline
                raw_items = await analyze(...)
                ...
                ontology = await build_ontology(...)
```

- [ ] **Step 3: Intercept `sim_checkpoint_data` in the event loop**

In the `async for event in run_simulation(...)` loop, add handling before `publish(event)`:

```python
            async for event in run_simulation(
                ...,
                checkpoint=existing_checkpoint,
            ):
                await checkpoint()
                if event["type"] == "sim_checkpoint_data":
                    # Enrich with analysis_md and raw_items (not available in social_runner)
                    await asyncio.to_thread(
                        save_checkpoint,
                        DB_PATH,
                        sim_id,
                        event["round_num"],
                        event["platform_states"],
                        event["personas"],
                        event["context_nodes"],
                        event["domain"] or domain_str,
                        analysis_md,
                        event["ontology"],
                        raw_items,
                    )
                    continue  # do NOT publish to Redis
                if event["type"] == "sim_report":
                    data = event["data"]
                    posts_by_platform = data.get("platform_states", {})
                    personas_by_platform = data.get("personas", {})
                    report_json = data.get("report_json", {})
                    report_md = data.get("markdown", "")
                publish(event)
```

- [ ] **Step 4: Delete checkpoint on successful completion**

After `save_sim_results(...)`, add:

```python
            await asyncio.to_thread(delete_checkpoint, DB_PATH, sim_id)
```

- [ ] **Step 5: Manual smoke test — verify checkpoint is saved during a short run**

Run a 2-round test simulation via the API (or a short Python script) and verify a row appears in `sim_checkpoints` after each round, then disappears on completion.

```bash
# Quick sanity check: inspect DB directly after a test run
sqlite3 noosphere.db "SELECT sim_id, last_round, saved_at FROM sim_checkpoints;"
```

- [ ] **Step 6: Commit**

```bash
git add backend/tasks.py
git commit -m "feat: intercept checkpoint events and restore from checkpoint on resume"
```

---

## Task 4: main.py — resume endpoint, status endpoint, Last-Event-ID SSE

**Files:**
- Modify: `backend/main.py`

- [ ] **Step 1: Add checkpoint imports to `main.py`**

Add `get_checkpoint`, `save_checkpoint`, `delete_checkpoint` to the import from `backend.db`:

```python
from backend.db import (
    init_db, create_simulation, update_simulation_status,
    get_sim_results, list_history, get_simulation, DB_PATH,
    count_active_simulations, reconcile_stale_simulations, request_simulation_cancel,
    get_checkpoint,
)
```

Also add `Request` to the FastAPI imports:

```python
from fastapi import FastAPI, HTTPException, Request
```

- [ ] **Step 2: Add `GET /simulate/{sim_id}/status` endpoint**

Add after the `/results/{sim_id}` endpoint:

```python
@app.get("/simulate/{sim_id}/status")
async def simulation_status(sim_id: str):
    """Return current simulation status and last checkpointed round."""
    sim = get_simulation(DB_PATH, sim_id)
    if not sim:
        raise HTTPException(404, "Simulation not found")
    checkpoint = get_checkpoint(DB_PATH, sim_id)
    return {
        "status": sim["status"],
        "last_round": checkpoint["last_round"] if checkpoint else 0,
    }
```

- [ ] **Step 3: Add `POST /simulate/{sim_id}/resume` endpoint**

Add after the status endpoint:

```python
@app.post("/simulate/{sim_id}/resume")
async def resume_simulation(sim_id: str):
    """Resume a failed simulation from its last checkpoint."""
    sim = get_simulation(DB_PATH, sim_id)
    if not sim:
        raise HTTPException(404, "Simulation not found")
    if sim["status"] != "failed":
        raise HTTPException(400, f"Only failed simulations can be resumed (status: {sim['status']})")
    checkpoint = get_checkpoint(DB_PATH, sim_id)
    if not checkpoint:
        raise HTTPException(409, "No checkpoint available; start a new simulation")

    # Atomic guard: only succeeds if status is still 'failed'
    updated = update_simulation_status(
        DB_PATH, sim_id, "running",
        allowed_current_statuses={"failed"},
    )
    if not updated:
        raise HTTPException(409, "Simulation state changed; try again")

    config = json.loads(sim["config_json"])
    try:
        run_simulation_task.apply_async(args=[sim_id, config], task_id=sim_id)
    except Exception:
        update_simulation_status(DB_PATH, sim_id, "failed", allowed_current_statuses={"running"})
        raise

    return {"sim_id": sim_id, "resuming_from_round": checkpoint["last_round"] + 1}
```

- [ ] **Step 4: Update SSE endpoint to support `last_id` query param for reconnect**

`EventSource` does not support custom headers, so `Last-Event-ID` is only sent by the browser on its own native reconnect — not when JavaScript creates a new `EventSource(url)`. To support efficient reconnect (no duplicate events), the frontend will pass the last received Redis stream ID as `?last_id=xxx` query param. The server reads this instead of the header.

Replace the existing `simulate_stream` function:

```python
@app.get("/simulate-stream/{sim_id}")
async def simulate_stream(sim_id: str, request: Request, last_id: str = "0"):
    """SSE stream backed by Redis Streams.
    last_id: Redis stream ID to resume from (pass "0" to replay all, omit for default).
    """
    sim = get_simulation(DB_PATH, sim_id)
    if not sim:
        raise HTTPException(404, "Simulation not found")

    stream_key = STREAM_KEY.format(sim_id)
    start_id = last_id or "0"

    async def event_generator():
        r = aioredis.from_url(REDIS_URL, decode_responses=True)
        current_id = start_id
        try:
            while True:
                results = await r.xread({stream_key: current_id}, count=100, block=30_000)
                if not results:
                    yield 'data: {"type":"heartbeat"}\n\n'
                    continue
                for _stream_name, messages in results:
                    for msg_id, fields in messages:
                        current_id = msg_id
                        raw = fields["data"]
                        yield f"id: {msg_id}\ndata: {raw}\n\n"
                        if json.loads(raw).get("type") == "sim_done":
                            return
        except Exception:
            return
        finally:
            await r.aclose()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
```

Note: FastAPI automatically parses `last_id` from query params (e.g., `/simulate-stream/{sim_id}?last_id=1234567890-0`). Default is `"0"` for fresh connections.

- [ ] **Step 5: Commit**

```bash
git add backend/main.py
git commit -m "feat: add resume and status endpoints, Last-Event-ID SSE support"
```

---

## Task 5: Frontend — API functions

**Files:**
- Modify: `frontend/src/api.ts`

- [ ] **Step 1: Add `resumeSimulation` and `getSimulationStatus` to `api.ts`**

Append to `frontend/src/api.ts`:

```typescript
const API_BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

export async function resumeSimulation(sim_id: string): Promise<{ sim_id: string; resuming_from_round: number }> {
  const res = await fetch(`${API_BASE}/simulate/${sim_id}/resume`, { method: 'POST' })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.detail ?? `Resume failed: ${res.status}`)
  }
  return res.json()
}

export async function getSimulationStatus(sim_id: string): Promise<{ status: string; last_round: number }> {
  const res = await fetch(`${API_BASE}/simulate/${sim_id}/status`)
  if (!res.ok) throw new Error(`Status check failed: ${res.status}`)
  return res.json()
}
```

Note: `API_BASE` is already declared at line 1 of `api.ts`. Do NOT add a second `const API_BASE` declaration — just append the two export functions after the existing `cancelSimulation` function.

- [ ] **Step 2: Commit**

```bash
git add frontend/src/api.ts
git commit -m "feat: add resumeSimulation and getSimulationStatus API functions"
```

---

## Task 6: Frontend — SSE auto-reconnect in `useSimulation.ts`

**Files:**
- Modify: `frontend/src/hooks/useSimulation.ts`

- [ ] **Step 1: Update `SimEvent` type to include `sim_resume`**

In the `SimEvent` union type, add:

```typescript
| { type: 'sim_resume'; from_round: number }
```

- [ ] **Step 2: Add `lastRound` to `SimState` interface**

```typescript
interface SimState {
  // ... existing fields ...
  lastRound: number          // last checkpointed round (from /status or sim_resume)
}
```

Initialize to `0` in `useState`.

- [ ] **Step 3: Replace the `useEffect` body with reconnect logic**

Key design: `EventSource` cannot send custom headers, so `Last-Event-ID` is only sent by the browser on its own native reconnect. When JS creates a new `EventSource(url)`, it must pass the last Redis stream ID as `?last_id=xxx` query param to avoid replaying duplicate events.

Add a `useRef` for the last received stream ID at the top of the hook (inside the function, before `useState`):

```typescript
  const lastEventIdRef = useRef<string>('0')
```

(Import `useRef` alongside `useEffect` and `useState` at the top of the file.)

Replace the entire `useEffect` body (lines 53–107) with:

```typescript
  useEffect(() => {
    if (!simId) return
    const API_BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'
    const RECONNECT_DELAYS = [1000, 2000, 4000, 8000, 16000, 30000]
    const MAX_RETRIES = RECONNECT_DELAYS.length
    let retryCount = 0
    let stopped = false
    let currentEs: EventSource | null = null

    function connect() {
      if (stopped) return
      // Pass last received stream ID so server resumes from that position
      const lastId = lastEventIdRef.current
      const url = lastId !== '0'
        ? `${API_BASE}/simulate-stream/${simId}?last_id=${encodeURIComponent(lastId)}`
        : `${API_BASE}/simulate-stream/${simId}`
      const es = new EventSource(url)
      currentEs = es

      es.onmessage = (e) => {
        retryCount = 0
        // SSE spec: the id: field is available on the MessageEvent
        if (e.lastEventId) lastEventIdRef.current = e.lastEventId
        const event: SimEvent = JSON.parse(e.data)
        setState(prev => {
          const next = { ...prev, events: [...prev.events, event] }
          if (event.type === 'sim_start') {
            next.status = 'running'
            next.agentCount = event.agent_count
          } else if (event.type === 'sim_resume') {
            next.status = 'running'
          } else if (event.type === 'sim_source_item') {
            next.sourceTimeline = [
              { source: event.source, title: event.title, snippet: event.snippet },
              ...prev.sourceTimeline,
            ]
          } else if (event.type === 'sim_platform_post') {
            const platform = event.post.platform
            const posts = { ...prev.postsByPlatform }
            posts[platform] = [...(posts[platform] || []), event.post]
            next.postsByPlatform = posts
          } else if (event.type === 'sim_round_summary') {
            next.roundNum = event.round_num
          } else if (event.type === 'sim_persona') {
            next.personaCount = prev.personaCount + 1
          } else if (event.type === 'sim_analysis') {
            next.analysisMd = event.data.markdown
          } else if (event.type === 'sim_ontology') {
            next.ontology = event.data
          } else if (event.type === 'sim_report') {
            next.report = (event.data as Record<string, unknown>).report_json as Record<string, unknown>
            next.personas = (event.data as Record<string, unknown>).personas as Record<string, unknown>
          } else if (event.type === 'sim_progress') {
            if (event.message.toLowerCase().includes('searching') || event.message.toLowerCase().includes('sources')) {
              next.isSourcing = true
            }
          } else if (event.type === 'sim_error') {
            next.status = 'error'
            next.errorMsg = event.message
          } else if (event.type === 'sim_done') {
            if (prev.status !== 'error') next.status = 'done'
            stopped = true
            es.close()
          }
          return next
        })
      }

      es.onerror = () => {
        es.close()
        if (stopped) return
        if (retryCount >= MAX_RETRIES) {
          setState(prev => ({ ...prev, status: 'error', errorMsg: 'Connection lost' }))
          return
        }
        const delay = RECONNECT_DELAYS[retryCount]
        retryCount++
        setTimeout(connect, delay)
      }
    }

    connect()
    return () => {
      stopped = true
      currentEs?.close()
    }
  }, [simId])
```

Also add `lastRound: 0` to the initial state and handle fetching `lastRound` from `/status` when `status === 'error'`. Add a `useEffect` that fires when `status` changes to `'error'`:

```typescript
  // Fetch last_round from /status when error occurs, for the Resume button
  useEffect(() => {
    if (state.status !== 'error' || !simId) return
    const API_BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'
    fetch(`${API_BASE}/simulate/${simId}/status`)
      .then(r => r.ok ? r.json() : null)
      .then(data => {
        if (data?.last_round > 0) {
          setState(prev => ({ ...prev, lastRound: data.last_round }))
        }
      })
      .catch(() => {})
  }, [state.status, simId])
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/hooks/useSimulation.ts
git commit -m "feat: SSE auto-reconnect with exponential backoff and sim_resume support"
```

---

## Task 7: Frontend — Resume button in `SimulatePage.tsx`

**Files:**
- Modify: `frontend/src/pages/SimulatePage.tsx`

- [ ] **Step 1: Import `resumeSimulation` in `SimulatePage.tsx`**

Add to imports:

```typescript
import { resumeSimulation } from '../api'
import { useState } from 'react'
```

(Note: `useEffect` is already imported.)

- [ ] **Step 2: Add resume handler and state**

Inside `SimulatePage()`, before the `return`:

```typescript
  const [isResuming, setIsResuming] = useState(false)
  const [resumeError, setResumeError] = useState<string | null>(null)

  async function handleResume() {
    if (!simId) return
    setIsResuming(true)
    setResumeError(null)
    try {
      await resumeSimulation(simId)
      // SSE will auto-reconnect; status transitions back to 'running' via sim_resume event
    } catch (e) {
      setResumeError(e instanceof Error ? e.message : 'Resume failed')
    } finally {
      setIsResuming(false)
    }
  }
```

- [ ] **Step 3: Replace the error display block in the feed panel**

Find this existing block in `SimulatePage.tsx` (around line 87–89):

```tsx
      {sim.status === 'error' && (
        <p style={{ color: '#ef4444', fontSize: 14, margin: '8px 0 20px' }}>{sim.errorMsg}</p>
      )}
```

Replace with:

```tsx
      {sim.status === 'error' && (
        <div style={{ margin: '8px 0 20px' }}>
          <p style={{ color: '#ef4444', fontSize: 14, margin: '0 0 12px' }}>{sim.errorMsg}</p>
          {sim.lastRound > 0 && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <p style={{ fontSize: 13, color: '#64748b', margin: 0 }}>
                {sim.lastRound}라운드까지 저장됨
              </p>
              <button
                onClick={handleResume}
                disabled={isResuming}
                style={{
                  padding: '8px 18px', borderRadius: 8, border: 'none',
                  background: '#6366f1', color: '#fff', fontWeight: 600,
                  fontSize: 14, cursor: isResuming ? 'not-allowed' : 'pointer',
                  opacity: isResuming ? 0.7 : 1,
                }}
              >
                {isResuming ? '재개 중...' : `${sim.lastRound + 1}라운드부터 재개하기`}
              </button>
            </div>
          )}
          {resumeError && (
            <p style={{ color: '#ef4444', fontSize: 13, margin: '8px 0 0' }}>{resumeError}</p>
          )}
        </div>
      )}
```

- [ ] **Step 4: Fix the missing `SocialPost` type import if TypeScript complains**

Check if `SocialPost` is imported at the top. It's used at line 113 in the existing file. If missing, add:

```typescript
import type { Platform, SocialPost } from '../types'
```

- [ ] **Step 5: Run TypeScript type check**

```bash
cd /Users/taeyoungpark/Desktop/noosphere/frontend
npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/SimulatePage.tsx
git commit -m "feat: add resume button to simulation error state"
```

---

## Task 8: End-to-end verification

- [ ] **Step 1: Run all backend tests**

```bash
cd /Users/taeyoungpark/Desktop/noosphere
python -m pytest backend/tests/ -v
```

Expected: all tests PASS.

- [ ] **Step 2: Start services and run a simulation**

```bash
# In separate terminals:
# Terminal 1: Redis
redis-server

# Terminal 2: Celery worker
cd /Users/taeyoungpark/Desktop/noosphere
celery -A backend.celery_app worker --loglevel=info

# Terminal 3: FastAPI
uvicorn backend.main:app --reload

# Terminal 4: Frontend
cd frontend && npm run dev
```

- [ ] **Step 3: Verify checkpoint is written after each round**

During a running simulation:

```bash
sqlite3 noosphere.db "SELECT sim_id, last_round, saved_at FROM sim_checkpoints;"
```

Expected: a row appears and `last_round` increments after each round.

- [ ] **Step 4: Verify checkpoint is deleted on completion**

After simulation completes:

```bash
sqlite3 noosphere.db "SELECT * FROM sim_checkpoints;"
```

Expected: empty result (row was deleted).

- [ ] **Step 5: Simulate a worker crash and verify resume**

Start a simulation. After round 3, kill the Celery worker:

```bash
kill -9 <celery_worker_pid>
```

Wait 90 seconds for heartbeat timeout → DB status changes to `failed`. In the UI, verify:
- Error state shows "3라운드까지 저장됨"
- "4라운드부터 재개하기" button appears

Restart Celery worker, click resume, verify simulation continues from round 4.

- [ ] **Step 6: Verify SSE auto-reconnect**

During a running simulation, temporarily kill the backend (`Ctrl+C`) and restart within 30 seconds. Verify the frontend automatically reconnects and resumes receiving events.

- [ ] **Step 7: Final commit**

```bash
git add -A
git commit -m "feat: simulation checkpoint and resume — complete implementation"
```
