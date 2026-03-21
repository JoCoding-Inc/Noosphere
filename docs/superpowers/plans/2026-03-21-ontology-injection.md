# Ontology Injection + UI Graph Visualization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate a shared domain ontology from collected context nodes before simulation, inject it into all agents, and visualize it as an interactive graph during simulation.

**Architecture:** One LLM call in `tasks.py` converts context_nodes into a structured ontology (entities + relationships). The ontology is passed through the simulation call chain and sliced per injection site. The `sim_ontology` SSE event carries it to the frontend where `react-force-graph-2d` renders it.

**Tech Stack:** Python (asyncio, backend LLM wrapper), React + TypeScript, react-force-graph-2d

---

## File Map

**Create:**
- `backend/ontology_builder.py` — `build_ontology()` + 3 slice functions + ID/source_node_ids assignment
- `frontend/src/components/OntologyGraph.tsx` — force-graph component with legend + side panel
- `tests/test_ontology_builder.py` — unit tests for builder and slice functions

**Modify:**
- `backend/tasks.py` — call `build_ontology()` after context_nodes, publish `sim_ontology`, pass ontology to `run_simulation()`
- `backend/simulation/social_runner.py` — add `ontology` param to `run_simulation()` and `collect_personas_for_platform()` local wrapper
- `backend/simulation/social_rounds.py` — add `ontology` param to `round_personas()`, `platform_round()`, `decide_action()`, `generate_content()`
- `backend/simulation/persona_generator.py` — add `ontology` param to `generate_persona()`, inject `ontology_for_persona()`
- `frontend/src/types.ts` — add `OntologyEntity`, `OntologyRelationship`, `OntologyData` interfaces
- `frontend/src/hooks/useSimulation.ts` — add `sim_ontology` to `SimEvent` union + `ontology` to `SimState`
- `frontend/src/pages/SimulatePage.tsx` — render `OntologyGraph` when ontology is available

---

## Task 1: Create `backend/ontology_builder.py`

**Files:**
- Create: `backend/ontology_builder.py`
- Create: `tests/test_ontology_builder.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_ontology_builder.py
import pytest
from backend.ontology_builder import (
    _assign_ids,
    _assign_source_node_ids,
    ontology_for_persona,
    ontology_for_action,
    ontology_for_content,
)

SAMPLE_ENTITIES_RAW = [
    {"name": "LangChain", "type": "framework"},
    {"name": "Pinecone", "type": "infrastructure"},
    {"name": "RAG", "type": "technology"},
]

SAMPLE_RELS = [
    {"from": "e0", "to": "e1", "type": "integrates_with"},
    {"from": "e0", "to": "e2", "type": "competes_with"},
]

SAMPLE_ONTOLOGY = {
    "domain_summary": "AI application development tooling",
    "entities": [
        {"id": "e0", "name": "LangChain", "type": "framework", "source_node_ids": ["n1"]},
        {"id": "e1", "name": "Pinecone", "type": "infrastructure", "source_node_ids": []},
        {"id": "e2", "name": "RAG", "type": "technology", "source_node_ids": []},
    ],
    "relationships": SAMPLE_RELS,
    "market_tensions": ["open-source vs managed"],
    "key_trends": ["LLM adoption"],
}


def test_assign_ids():
    entities = _assign_ids(SAMPLE_ENTITIES_RAW)
    assert entities[0]["id"] == "e0"
    assert entities[1]["id"] == "e1"
    assert entities[2]["id"] == "e2"
    # LLM-provided IDs should not be present in raw input
    assert "id" not in SAMPLE_ENTITIES_RAW[0]


def test_assign_source_node_ids_case_insensitive():
    context_nodes = [
        {"id": "n1", "title": "LangChain Python library", "source": "github", "abstract": "..."},
        {"id": "n2", "title": "Pinecone vector DB", "source": "hackernews", "abstract": "..."},
    ]
    entities = _assign_ids(SAMPLE_ENTITIES_RAW)
    entities = _assign_source_node_ids(entities, context_nodes)
    assert "n1" in entities[0]["source_node_ids"]  # LangChain matches
    assert "n2" in entities[1]["source_node_ids"]  # Pinecone matches
    assert entities[2]["source_node_ids"] == []     # RAG no match


def test_ontology_for_persona_under_400_chars():
    result = ontology_for_persona(SAMPLE_ONTOLOGY)
    assert len(result) <= 400
    assert "AI application development tooling" in result
    assert "LangChain" in result
    assert "open-source vs managed" in result


def test_ontology_for_action_under_200_chars():
    result = ontology_for_action(SAMPLE_ONTOLOGY)
    assert len(result) <= 200
    assert "AI application development tooling" in result


def test_ontology_for_content_under_600_chars():
    result = ontology_for_content(SAMPLE_ONTOLOGY)
    assert len(result) <= 600
    assert "LangChain" in result
    assert "integrates_with" in result or "Pinecone" in result
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/taeyoungpark/Desktop/noosphere
python -m pytest tests/test_ontology_builder.py -v 2>&1 | head -30
```

Expected: `ModuleNotFoundError: No module named 'backend.ontology_builder'`

- [ ] **Step 3: Create `backend/ontology_builder.py`**

```python
# backend/ontology_builder.py
from __future__ import annotations
import json
import logging
import re

from backend import llm

logger = logging.getLogger(__name__)

ENTITY_TYPES = [
    "framework", "product", "company", "technology", "concept",
    "market_segment", "pain_point", "research", "standard", "regulation",
]
RELATIONSHIP_TYPES = [
    "competes_with", "integrates_with", "built_on", "targets",
    "addresses", "enables", "regulated_by", "part_of",
]

_SYSTEM = (
    "You are a domain knowledge analyst. Given a list of collected knowledge nodes "
    "and a product idea, extract the key entities and relationships that form the "
    "domain ecosystem relevant to evaluating this idea."
)


async def build_ontology(
    context_nodes: list[dict],
    input_text: str,
    provider: str = "openai",
) -> dict | None:
    """
    Generate a domain ontology from context_nodes.
    Returns ontology dict or None on failure.
    """
    nodes_text = "\n".join(
        f"- [{n.get('source', '')}] {n.get('title', '')} — {(n.get('abstract') or '')[:150]}"
        for n in context_nodes[:30]
    )
    prompt = (
        f"Idea being evaluated: {input_text[:500]}\n\n"
        f"Collected knowledge nodes:\n{nodes_text}\n\n"
        f"Extract entities and relationships from this ecosystem. "
        f"Focus on what is relevant to evaluating the idea above.\n\n"
        f"Entity types allowed: {', '.join(ENTITY_TYPES)}\n"
        f"Relationship types allowed: {', '.join(RELATIONSHIP_TYPES)}\n\n"
        f"Return ONLY valid JSON with this exact structure (no IDs in entities):\n"
        f'{{"domain_summary": "...", '
        f'"entities": [{{"name": "...", "type": "..."}}], '
        f'"relationships": [{{"from_name": "...", "to_name": "...", "type": "..."}}], '
        f'"market_tensions": ["..."], '
        f'"key_trends": ["..."]}}'
    )
    try:
        response = await llm.complete(
            messages=[
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": prompt},
            ],
            tier="mid",
            provider=provider,
            max_tokens=2048,
        )
        raw = (response.content or "").strip()
        raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.DOTALL).strip()
        if not raw:
            raise ValueError("Empty response")
        parsed = json.loads(raw)
    except Exception as exc:
        logger.warning("build_ontology failed: %s", exc)
        return None

    # Assign IDs backend-side
    raw_entities = parsed.get("entities", [])
    entities = _assign_ids(raw_entities)

    # Resolve relationship from_name/to_name → entity IDs
    name_to_id = {e["name"].lower(): e["id"] for e in entities}
    relationships = []
    for rel in parsed.get("relationships", []):
        from_id = name_to_id.get((rel.get("from_name") or "").lower())
        to_id = name_to_id.get((rel.get("to_name") or "").lower())
        if from_id and to_id and rel.get("type") in RELATIONSHIP_TYPES:
            relationships.append({"from": from_id, "to": to_id, "type": rel["type"]})

    # source_node_ids assigned separately (needs context_nodes passed in)
    entities = _assign_source_node_ids(entities, context_nodes)

    return {
        "domain_summary": str(parsed.get("domain_summary", ""))[:200],
        "entities": entities,
        "relationships": relationships,
        "market_tensions": [str(t) for t in parsed.get("market_tensions", [])[:5]],
        "key_trends": [str(t) for t in parsed.get("key_trends", [])[:5]],
    }


def _assign_ids(entities: list[dict]) -> list[dict]:
    """Assign sequential IDs e0, e1, ... to entities (modifies copies)."""
    return [{**e, "id": f"e{i}"} for i, e in enumerate(entities)]


def _assign_source_node_ids(entities: list[dict], context_nodes: list[dict]) -> list[dict]:
    """
    Populate source_node_ids via case-insensitive substring match:
    entity.name.lower() in node["title"].lower()
    """
    result = []
    for entity in entities:
        name_lower = entity["name"].lower()
        matched = [
            n["id"] for n in context_nodes
            if name_lower in n.get("title", "").lower()
        ]
        result.append({**entity, "source_node_ids": matched})
    return result


# ── Slice functions ────────────────────────────────────────────────────────────

def ontology_for_persona(ontology: dict) -> str:
    """max 400 chars — domain_summary + top 8 entity names + market_tensions."""
    domain = ontology.get("domain_summary", "")
    names = ", ".join(
        f"{e['name']} ({e['type']})"
        for e in ontology.get("entities", [])[:8]
    )
    tensions = "; ".join(ontology.get("market_tensions", [])[:3])
    text = f"Domain: {domain}\nKey players: {names}"
    if tensions:
        text += f"\nMarket tensions: {tensions}"
    return text[:400]


def ontology_for_action(ontology: dict) -> str:
    """max 200 chars — domain_summary + top 5 entity names only."""
    domain = ontology.get("domain_summary", "")
    names = ", ".join(e["name"] for e in ontology.get("entities", [])[:5])
    text = f"Domain: {domain}\nPlayers: {names}"
    return text[:200]


def ontology_for_content(ontology: dict) -> str:
    """max 600 chars — entity name list + relationship summary."""
    names = ", ".join(
        f"{e['name']} ({e['type']})"
        for e in ontology.get("entities", [])
    )
    id_to_name = {e["id"]: e["name"] for e in ontology.get("entities", [])}
    rels = "\n".join(
        f"- {id_to_name.get(r['from'], r['from'])} {r['type']} {id_to_name.get(r['to'], r['to'])}"
        for r in ontology.get("relationships", [])[:10]
    )
    text = f"Players: {names}"
    if rels:
        text += f"\nRelationships:\n{rels}"
    return text[:600]
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_ontology_builder.py -v
```

Expected: All 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/ontology_builder.py tests/test_ontology_builder.py
git commit -m "feat: add ontology_builder with build_ontology and slice functions"
```

---

## Task 2: Wire ontology into `tasks.py`

**Files:**
- Modify: `backend/tasks.py` (lines 149–181)

- [ ] **Step 1: Add import and call `build_ontology` in tasks.py**

In `backend/tasks.py`, after the `context_nodes` block (after line 164) and before the `publish(sim_progress...)` call, add:

```python
# After context_nodes is built (after line 164):
from backend.ontology_builder import build_ontology

publish({"type": "sim_progress", "message": "Building ecosystem ontology..."})
ontology = await build_ontology(
    context_nodes=context_nodes,
    input_text=config["input_text"],
    provider=provider,
)
if ontology:
    publish({"type": "sim_ontology", "data": ontology})
```

Then update the `run_simulation(...)` call to pass `ontology=ontology`:

```python
async for event in run_simulation(
    input_text=config["input_text"],
    context_nodes=context_nodes,
    domain=domain_str,
    max_agents=config["max_agents"],
    num_rounds=config["num_rounds"],
    platforms=config["platforms"],
    language=config["language"],
    activation_rate=config["activation_rate"],
    provider=provider,
    ontology=ontology,       # ← add this
):
```

- [ ] **Step 2: Verify tasks.py is syntactically valid**

```bash
python -c "import backend.tasks; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/tasks.py
git commit -m "feat: call build_ontology in task and stream sim_ontology event"
```

---

## Task 3: Thread ontology through `social_runner.py`

**Files:**
- Modify: `backend/simulation/social_runner.py`

- [ ] **Step 1: Write a failing test**

```python
# In tests/test_social_runner.py, add:
@pytest.mark.asyncio
async def test_run_simulation_accepts_ontology_param():
    """run_simulation should accept ontology kwarg without error."""
    from backend.simulation.social_runner import run_simulation

    fake_ontology = {
        "domain_summary": "test domain",
        "entities": [],
        "relationships": [],
        "market_tensions": [],
        "key_trends": [],
    }

    events = []
    async for event in run_simulation(
        input_text="A SaaS app",
        context_nodes=FAKE_NODES,
        domain="saas",
        max_agents=2,
        num_rounds=1,
        platforms=["hackernews"],
        language="English",
        ontology=fake_ontology,
    ):
        events.append(event)
        if event["type"] in ("sim_done", "sim_error"):
            break

    assert any(e["type"] == "sim_start" for e in events)
```

- [ ] **Step 2: Run to verify it fails**

```bash
python -m pytest tests/test_social_runner.py::test_run_simulation_accepts_ontology_param -v
```

Expected: `TypeError: run_simulation() got an unexpected keyword argument 'ontology'`

- [ ] **Step 3: Update `social_runner.py`**

In `run_simulation()` signature (line 19), add `ontology: dict | None = None`:

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
    ontology: dict | None = None,      # ← add
) -> AsyncGenerator[dict, None]:
```

Update `collect_personas_for_platform` (the local async wrapper at lines 55–68) to accept and forward ontology:

```python
async def collect_personas_for_platform(platform_name: str) -> list[tuple[dict, Persona]]:
    results = []
    async for event in round_personas(
        nodes, idea_text,
        adjacency=adjacency, id_to_node=id_to_node,
        platform_name=platform_name,
        provider=provider,
        ontology=ontology,      # ← add
    ):
        ...
```

Update `run_platform_round` (the local async at line 112) to pass ontology to `platform_round`:

```python
async def run_platform_round(plat, rn=round_num):
    ...
    async for event in platform_round(
        plat, state, plat_personas, degree, idea_text, rn, language, activation_rate,
        provider=provider,
        ontology=ontology,      # ← add
    ):
        ...
```

- [ ] **Step 4: Run all social_runner tests**

```bash
python -m pytest tests/test_social_runner.py -v
```

Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/simulation/social_runner.py tests/test_social_runner.py
git commit -m "feat: thread ontology param through social_runner"
```

---

## Task 4: Inject ontology in `social_rounds.py`

**Files:**
- Modify: `backend/simulation/social_rounds.py`

- [ ] **Step 1: Write failing tests**

```python
# In tests/test_social_rounds.py, add:
FAKE_ONTOLOGY = {
    "domain_summary": "SaaS tools",
    "entities": [{"id": "e0", "name": "SaaS", "type": "concept", "source_node_ids": []}],
    "relationships": [],
    "market_tensions": ["build vs buy"],
    "key_trends": [],
}

@pytest.mark.asyncio
async def test_decide_action_accepts_ontology():
    """decide_action should accept ontology kwarg."""
    from backend.simulation.social_rounds import decide_action
    from backend.simulation.models import Persona
    from unittest.mock import AsyncMock, patch
    from backend.llm import LLMResponse

    persona = Persona(
        node_id="n1", name="Alice", role="Engineer", age=30,
        seniority="mid", affiliation="individual", company="X",
        mbti="INTJ", interests=["tech"], skepticism=5,
        commercial_focus=5, innovation_openness=5, source_title="test",
    )
    mock_resp = LLMResponse(content=None, tool_name="decide_action",
                            tool_args={"action_type": "post", "target_post_id": None})
    with patch("backend.simulation.social_rounds.llm") as mock_llm:
        mock_llm.complete = AsyncMock(return_value=mock_resp)
        from backend.simulation.platforms.hackernews import HackerNews
        plat = HackerNews()
        result = await decide_action(persona, plat, "feed text", ontology=FAKE_ONTOLOGY)
    assert result.action_type == "post"


@pytest.mark.asyncio
async def test_generate_content_accepts_ontology():
    """generate_content should accept ontology kwarg."""
    from backend.simulation.social_rounds import generate_content, AgentAction
    from backend.simulation.models import Persona
    from unittest.mock import AsyncMock, patch
    from backend.llm import LLMResponse

    persona = Persona(
        node_id="n1", name="Alice", role="Engineer", age=30,
        seniority="mid", affiliation="individual", company="X",
        mbti="INTJ", interests=["tech"], skepticism=5,
        commercial_focus=5, innovation_openness=5, source_title="test",
    )
    action = AgentAction(action_type="post", target_post_id=None)
    mock_resp = LLMResponse(content=None, tool_name="write_post",
                            tool_args={"title": "test", "body": "body", "tags": []})
    with patch("backend.simulation.social_rounds.llm") as mock_llm:
        mock_llm.complete = AsyncMock(return_value=mock_resp)
        from backend.simulation.platforms.hackernews import HackerNews
        plat = HackerNews()
        content, _ = await generate_content(
            persona, action, plat, "feed", "idea", ontology=FAKE_ONTOLOGY
        )
    assert isinstance(content, str)
```

- [ ] **Step 2: Run to verify they fail**

```bash
python -m pytest tests/test_social_rounds.py::test_decide_action_accepts_ontology tests/test_social_rounds.py::test_generate_content_accepts_ontology -v
```

Expected: `TypeError: ... got an unexpected keyword argument 'ontology'`

- [ ] **Step 3: Update `social_rounds.py`**

Add `ontology: dict | None = None` param to `round_personas`, `platform_round`, `decide_action`, `generate_content`.

Import slice functions at top:

```python
from backend.ontology_builder import ontology_for_persona, ontology_for_action, ontology_for_content
```

In `decide_action()`, add ontology injection before the final prompt:

```python
async def decide_action(
    persona: Persona,
    platform: AbstractPlatform,
    feed_text: str,
    language: str = "English",
    provider: str = "openai",
    ontology: dict | None = None,      # ← add
) -> AgentAction:
    ...
    # After building base prompt, before the LLM call:
    if ontology:
        prompt += f"\nEcosystem context:\n{ontology_for_action(ontology)}"
    ...
```

In `generate_content()`, add ontology injection:

```python
async def generate_content(
    persona: Persona,
    action: AgentAction,
    platform: AbstractPlatform,
    feed_text: str,
    idea_text: str,
    language: str = "English",
    provider: str = "openai",
    ontology: dict | None = None,      # ← add
) -> tuple[str, dict]:
    ...
    # After building base prompt, before the LLM call:
    if ontology:
        prompt += f"\nEcosystem context:\n{ontology_for_content(ontology)}"
    ...
```

In `round_personas()`:

```python
async def round_personas(
    nodes, idea_text, concurrency=4, adjacency=None,
    id_to_node=None, platform_name="", provider="openai",
    ontology: dict | None = None,      # ← add
) -> AsyncGenerator[dict, None]:
    ...
    # Pass to generate_persona:
    persona = await generate_persona(
        node,
        idea_text=idea_text,
        neighbor_titles=neighbor_titles,
        platform_name=platform_name,
        provider=provider,
        ontology=ontology,      # ← add
    )
```

In `platform_round()`:

```python
async def platform_round(
    platform, state, personas, degree, idea_text,
    round_num, language="English", activation_rate=0.25,
    provider="openai",
    ontology: dict | None = None,      # ← add
) -> AsyncGenerator[dict, None]:
    ...
    # Pass to decide_action and generate_content:
    action = await decide_action(persona, platform, feed_text, language, provider=provider, ontology=ontology)
    ...
    content, structured_data = await generate_content(
        persona, action, platform, feed_text, idea_text, language,
        provider=provider, ontology=ontology
    )
```

- [ ] **Step 4: Run all social_rounds tests**

```bash
python -m pytest tests/test_social_rounds.py -v
```

Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/simulation/social_rounds.py tests/test_social_rounds.py
git commit -m "feat: inject ontology into decide_action and generate_content prompts"
```

---

## Task 5: Inject ontology in `persona_generator.py`

**Files:**
- Modify: `backend/simulation/persona_generator.py`
- Modify: `tests/test_persona_generator.py`

- [ ] **Step 1: Write a failing test**

In `tests/test_persona_generator.py`, add:

```python
@pytest.mark.asyncio
async def test_generate_persona_with_ontology_injects_context():
    """Ontology context should appear in the prompt sent to LLM."""
    from unittest.mock import AsyncMock, patch, call
    from backend.llm import LLMResponse

    tool_args = {
        "name": "Alice Chen", "role": "Engineer", "age": 28,
        "seniority": "mid", "affiliation": "individual",
        "company": "TechCorp", "mbti": "INTJ",
        "interests": ["AI"], "skepticism": 3,
        "commercial_focus": 5, "innovation_openness": 8,
    }
    fake_ontology = {
        "domain_summary": "RAG tooling ecosystem",
        "entities": [{"id": "e0", "name": "LangChain", "type": "framework", "source_node_ids": []}],
        "relationships": [],
        "market_tensions": ["build vs buy"],
        "key_trends": [],
    }
    mock_response = LLMResponse(content=None, tool_name="create_persona", tool_args=tool_args)

    captured_messages = []
    async def mock_complete(**kwargs):
        captured_messages.extend(kwargs.get("messages", []))
        return mock_response

    with patch("backend.simulation.persona_generator.llm") as mock_llm:
        mock_llm.complete = mock_complete
        from backend.simulation.persona_generator import generate_persona
        node = {"id": "node1", "title": "AI SaaS", "source": "arxiv", "abstract": "..."}
        await generate_persona(node, idea_text="RAG app", platform_name="hackernews",
                               provider="openai", ontology=fake_ontology)

    all_text = " ".join(m["content"] for m in captured_messages)
    assert "RAG tooling ecosystem" in all_text
```

- [ ] **Step 2: Run to verify it fails**

```bash
python -m pytest tests/test_persona_generator.py::test_generate_persona_with_ontology_injects_context -v
```

Expected: `TypeError: generate_persona() got an unexpected keyword argument 'ontology'`

- [ ] **Step 3: Update `persona_generator.py`**

Add import at top:
```python
from backend.ontology_builder import ontology_for_persona
```

Add `ontology: dict | None = None` to `generate_persona()` signature and inject before LLM call:

```python
async def generate_persona(
    node: dict,
    idea_text: str = "",
    neighbor_titles: list[str] | None = None,
    platform_name: str = "",
    provider: str = "openai",
    ontology: dict | None = None,      # ← add
) -> Persona:
    ...
    # After building prompt, before LLM call:
    if ontology:
        prompt += f"\n\nEcosystem context:\n{ontology_for_persona(ontology)}"
    ...
```

- [ ] **Step 4: Run all persona_generator tests**

```bash
python -m pytest tests/test_persona_generator.py -v
```

Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/simulation/persona_generator.py tests/test_persona_generator.py
git commit -m "feat: inject ontology_for_persona into generate_persona prompt"
```

---

## Task 6: Add frontend types to `types.ts`

**Files:**
- Modify: `frontend/src/types.ts`

- [ ] **Step 1: Add ontology interfaces at the end of `types.ts`**

```typescript
// ── Ontology types ────────────────────────────────────────────────────────────

export interface OntologyEntity {
  id: string            // "e0", "e1", ...
  name: string
  type: string          // framework | product | company | technology | concept | market_segment | pain_point | research | standard | regulation
  source_node_ids: string[]
}

export interface OntologyRelationship {
  from: string          // entity id
  to: string            // entity id
  type: string          // competes_with | integrates_with | built_on | targets | addresses | enables | regulated_by | part_of
}

export interface OntologyData {
  domain_summary: string
  entities: OntologyEntity[]
  relationships: OntologyRelationship[]
  market_tensions: string[]
  key_trends: string[]
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd /Users/taeyoungpark/Desktop/noosphere/frontend
npx tsc --noEmit
```

Expected: No errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/types.ts
git commit -m "feat: add OntologyEntity, OntologyRelationship, OntologyData types"
```

---

## Task 7: Update `useSimulation.ts` hook

**Files:**
- Modify: `frontend/src/hooks/useSimulation.ts`

- [ ] **Step 1: Add `sim_ontology` to `SimEvent` union type**

Update the import at the top of `useSimulation.ts` to include `OntologyData`:
```typescript
import type { Platform, SocialPost, OntologyData } from '../types'
```

Then add ONE new line to the existing `SimEvent` union — insert after the `sim_analysis` line:
```typescript
  | { type: 'sim_ontology'; data: OntologyData }           // ← add this line only
```

Do NOT replace the entire union — only add this single variant. The existing `sim_analysis` and all other variants must remain unchanged.

- [ ] **Step 2: Add `ontology` field to `SimState`**

```typescript
interface SimState {
  status: 'connecting' | 'running' | 'done' | 'error'
  events: SimEvent[]
  postsByPlatform: Partial<Record<Platform, SocialPost[]>>
  report: Record<string, unknown> | null
  personas: Record<string, unknown> | null
  analysisMd: string
  errorMsg: string
  roundNum: number
  agentCount: number
  personaCount: number
  sourceTimeline: SourceItem[]
  ontology: OntologyData | null     // ← add
}
```

- [ ] **Step 3: Initialize `ontology: null` in useState and handle the event**

In the `useState` initializer:
```typescript
const [state, setState] = useState<SimState>({
  ...
  ontology: null,     // ← add
})
```

In the `es.onmessage` handler, add:
```typescript
} else if (event.type === 'sim_ontology') {
  next.ontology = event.data
}
```

Note: `sim_ontology` arrives before `sim_start`, so `status` is still `'connecting'` when it fires. The state update above stores it regardless of current status — this is correct behavior.

- [ ] **Step 4: Verify TypeScript compiles**

```bash
cd /Users/taeyoungpark/Desktop/noosphere/frontend
npx tsc --noEmit
```

Expected: No errors.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/hooks/useSimulation.ts
git commit -m "feat: add sim_ontology event handling to useSimulation hook"
```

---

## Task 8: Create `OntologyGraph.tsx` component

**Files:**
- Create: `frontend/src/components/OntologyGraph.tsx`

- [ ] **Step 1: Install `react-force-graph-2d`**

```bash
cd /Users/taeyoungpark/Desktop/noosphere/frontend
npm install react-force-graph-2d
```

Verify install succeeded: `node_modules/react-force-graph-2d` should exist.

- [ ] **Step 2: Create the component**

```tsx
// frontend/src/components/OntologyGraph.tsx
import { useRef, useState, useCallback } from 'react'
import ForceGraph2D from 'react-force-graph-2d'
import type { OntologyEntity, OntologyRelationship, OntologyData } from '../types'

// ── Color mappings ────────────────────────────────────────────────────────────
const NODE_COLORS: Record<string, string> = {
  framework:      '#3b82f6', // blue
  product:        '#22c55e', // green
  company:        '#f97316', // orange
  technology:     '#a855f7', // purple
  market_segment: '#eab308', // yellow
  pain_point:     '#ef4444', // red
  research:       '#14b8a6', // teal
  standard:       '#94a3b8', // gray
  concept:        '#c084fc', // lavender
  regulation:     '#92400e', // brown
}

const EDGE_COLORS: Record<string, string> = {
  competes_with:   '#ef4444',
  integrates_with: '#22c55e',
  built_on:        '#3b82f6',
  targets:         '#f97316',
  addresses:       '#14b8a6',
  enables:         '#a855f7',
  regulated_by:    '#92400e',
  part_of:         '#94a3b8',
}

const EDGE_DASHED: Record<string, boolean> = {
  competes_with: true,
  regulated_by:  true,
}

interface GraphNode {
  id: string
  name: string
  type: string
  source_node_ids: string[]
  color: string
}

interface GraphLink {
  source: string
  target: string
  type: string
  color: string
}

interface SidePanelProps {
  entity: OntologyEntity | null
  contextNodes: Array<{ id: string; title: string; source: string; url?: string }>
  onClose: () => void
}

function SidePanel({ entity, contextNodes, onClose }: SidePanelProps) {
  if (!entity) return null
  const sources = contextNodes.filter(n => entity.source_node_ids.includes(n.id))
  return (
    <div style={{
      position: 'absolute', top: 0, right: 0, width: 240,
      height: '100%', background: '#fff', borderLeft: '1px solid #e2e8f0',
      padding: '16px', overflowY: 'auto', zIndex: 10,
    }}>
      <button onClick={onClose} style={{
        float: 'right', background: 'none', border: 'none',
        cursor: 'pointer', fontSize: 18, color: '#94a3b8',
      }}>×</button>
      <div style={{
        display: 'inline-block', padding: '2px 8px', borderRadius: 4,
        background: NODE_COLORS[entity.type] ?? '#94a3b8',
        color: '#fff', fontSize: 11, fontWeight: 600, marginBottom: 8,
      }}>
        {entity.type}
      </div>
      <h3 style={{ margin: '0 0 12px', fontSize: 15, fontWeight: 700 }}>{entity.name}</h3>
      {sources.length > 0 && (
        <>
          <p style={{ fontSize: 12, color: '#64748b', margin: '0 0 6px' }}>Sources:</p>
          {sources.map(s => (
            <div key={s.id} style={{ fontSize: 12, marginBottom: 4 }}>
              {s.url
                ? <a href={s.url} target="_blank" rel="noreferrer" style={{ color: '#6366f1' }}>{s.title}</a>
                : <span style={{ color: '#475569' }}>{s.title}</span>
              }
              <span style={{ color: '#94a3b8', marginLeft: 4 }}>({s.source})</span>
            </div>
          ))}
        </>
      )}
    </div>
  )
}

interface OntologyGraphProps {
  data: OntologyData
  contextNodes?: Array<{ id: string; title: string; source: string; url?: string }>
}

export function OntologyGraph({ data, contextNodes = [] }: OntologyGraphProps) {
  const [selectedEntity, setSelectedEntity] = useState<OntologyEntity | null>(null)
  const [hiddenTypes, setHiddenTypes] = useState<Set<string>>(new Set())

  const graphNodes: GraphNode[] = data.entities
    .filter(e => !hiddenTypes.has(e.type))
    .map(e => ({ ...e, color: NODE_COLORS[e.type] ?? '#94a3b8' }))

  const visibleIds = new Set(graphNodes.map(n => n.id))
  const graphLinks: GraphLink[] = data.relationships
    .filter(r => visibleIds.has(r.from) && visibleIds.has(r.to))
    .map(r => ({
      source: r.from,
      target: r.to,
      type: r.type,
      color: EDGE_COLORS[r.type] ?? '#cbd5e1',
    }))

  const usedTypes = [...new Set(data.entities.map(e => e.type))]

  const toggleType = useCallback((type: string) => {
    setHiddenTypes(prev => {
      const next = new Set(prev)
      next.has(type) ? next.delete(type) : next.add(type)
      return next
    })
  }, [])

  return (
    <div style={{ position: 'relative', border: '1px solid #e2e8f0', borderRadius: 12, overflow: 'hidden', background: '#f8fafc' }}>
      {/* Header */}
      <div style={{ padding: '12px 16px', borderBottom: '1px solid #e2e8f0', background: '#fff' }}>
        <p style={{ margin: 0, fontSize: 12, color: '#64748b' }}>{data.domain_summary}</p>
      </div>

      {/* Legend */}
      <div style={{ padding: '8px 16px', display: 'flex', gap: 8, flexWrap: 'wrap', borderBottom: '1px solid #e2e8f0', background: '#fff' }}>
        {usedTypes.map(type => (
          <button
            key={type}
            onClick={() => toggleType(type)}
            style={{
              display: 'flex', alignItems: 'center', gap: 4,
              padding: '2px 8px', borderRadius: 4, fontSize: 11,
              border: '1.5px solid ' + (NODE_COLORS[type] ?? '#94a3b8'),
              background: hiddenTypes.has(type) ? '#fff' : (NODE_COLORS[type] ?? '#94a3b8'),
              color: hiddenTypes.has(type) ? (NODE_COLORS[type] ?? '#94a3b8') : '#fff',
              cursor: 'pointer', fontWeight: 600, transition: 'all 0.15s',
            }}
          >
            {type}
          </button>
        ))}
      </div>

      {/* Graph */}
      <div style={{ position: 'relative', height: 400 }}>
        <ForceGraph2D
          graphData={{ nodes: graphNodes, links: graphLinks }}
          nodeId="id"
          nodeLabel="name"
          nodeColor="color"
          nodeRelSize={6}
          linkColor="color"
          linkDirectionalArrowLength={6}
          linkDirectionalArrowRelPos={1}
          linkLineDash={(link: GraphLink) => EDGE_DASHED[link.type] ? [4, 2] : undefined}
          onNodeClick={(node: GraphNode) => {
            const entity = data.entities.find(e => e.id === node.id)
            setSelectedEntity(entity ?? null)
          }}
          backgroundColor="#f8fafc"
          width={selectedEntity ? undefined : undefined}
        />
        <SidePanel
          entity={selectedEntity}
          contextNodes={contextNodes}
          onClose={() => setSelectedEntity(null)}
        />
      </div>
    </div>
  )
}
```

- [ ] **Step 3: Verify TypeScript compiles**

```bash
cd /Users/taeyoungpark/Desktop/noosphere/frontend
npx tsc --noEmit
```

Expected: No errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/OntologyGraph.tsx
git commit -m "feat: add OntologyGraph force-directed visualization component"
```

---

## Task 9: Wire `OntologyGraph` into `SimulatePage.tsx`

**Files:**
- Modify: `frontend/src/pages/SimulatePage.tsx`

- [ ] **Step 1: Import and render `OntologyGraph`**

Add import at top of `SimulatePage.tsx`:
```typescript
import { OntologyGraph } from '../components/OntologyGraph'
```

The file does NOT render `analysisMd`. The correct insertion point is between the source timeline block and the platform feed block. Insert before the `{/* 플랫폼별 시뮬레이션 피드 */}` comment (line 173 in current code):

```tsx
{/* Ecosystem Map — shown when ontology is available, after sourcing phase */}
{sim.ontology && (
  <div style={{ marginBottom: 32, animation: 'fadeInUp 0.4s ease' }}>
    <h3 style={{ fontSize: 15, fontWeight: 700, margin: '0 0 12px', letterSpacing: '-0.02em' }}>
      Ecosystem Map
    </h3>
    <OntologyGraph
      data={sim.ontology}
      contextNodes={[]}
    />
  </div>
)}

{/* 플랫폼별 시뮬레이션 피드 */}
```

Note: `contextNodes` is passed as empty array because `sourceTimeline` items do not carry backend node IDs — the side panel will show entity name/type only, without source links. This is a known limitation; source link resolution would require a separate backend change to carry node URLs through the SSE stream.

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd /Users/taeyoungpark/Desktop/noosphere/frontend
npx tsc --noEmit
```

Expected: No errors.

- [ ] **Step 3: Run frontend build to verify bundle**

```bash
npm run build 2>&1 | tail -20
```

Expected: Build succeeds. Check bundle size output — `react-force-graph-2d` should add ~60KB gzip.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/SimulatePage.tsx
git commit -m "feat: render OntologyGraph in SimulatePage when ontology is available"
```

---

## Task 10: Full integration smoke test

- [ ] **Step 1: Run the full backend test suite**

```bash
cd /Users/taeyoungpark/Desktop/noosphere
python -m pytest tests/ -v --tb=short 2>&1 | tail -30
```

Expected: All tests PASS. If any pre-existing tests fail unrelated to this feature, note them but do not fix them as part of this task.

- [ ] **Step 2: Verify ontology_builder import chain works end-to-end**

```bash
python -c "
from backend.ontology_builder import build_ontology, ontology_for_persona, ontology_for_action, ontology_for_content
from backend.simulation.social_runner import run_simulation
from backend.simulation.social_rounds import decide_action, generate_content, round_personas, platform_round
from backend.simulation.persona_generator import generate_persona
print('All imports OK')
"
```

Expected: `All imports OK`

- [ ] **Step 3: Final commit**

```bash
git add -A
git commit -m "feat: ontology injection — all backend wiring and frontend visualization complete"
```
