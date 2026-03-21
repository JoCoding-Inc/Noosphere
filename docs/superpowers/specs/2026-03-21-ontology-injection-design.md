# Ontology Injection + UI Graph Visualization Design

**Date:** 2026-03-21
**Scope:** Shared ontology generation from collected knowledge nodes, injection into all simulation agents, and interactive graph visualization in the UI.

---

## Problem

Currently, each simulation agent only knows about its own assigned context node plus adjacent node titles. The full set of collected knowledge (up to 30 nodes from HN, GitHub, arxiv, etc.) is never shared with agents. This means agents evaluate ideas without awareness of the broader ecosystem — competitors, enabling technologies, known pain points, or market tensions.

---

## Solution Overview

1. **Ontology generation** — one LLM call before simulation starts, converting all context_nodes into a structured knowledge graph (entities + relationships).
2. **Agent injection** — every agent receives a sliced view of this ontology relevant to their task (persona generation, idea reaction, content generation).
3. **UI graph visualization** — the ontology is streamed to the frontend and rendered as an interactive force-directed graph.

---

## Section 1: Backend — Ontology Generation

### New module: `backend/ontology_builder.py`

Called in `tasks.py` after `context_nodes` are built, before `run_simulation()`.

**Signature:** `build_ontology(context_nodes: list[dict], input_text: str, provider: str) -> dict | None`

- `context_nodes` — collected nodes with `id`, `title`, `source`, `abstract`
- `input_text` — the original user idea description, used to bias entity extraction toward the idea's domain (e.g., if the idea is about RAG, the LLM prioritizes RAG-related entities from context_nodes)
- `provider` — LLM provider string passed through from task config

**Output:** ontology dict, or `None` on failure (see Error Handling below)

**Output schema:**

```json
{
  "domain_summary": "One sentence describing the domain landscape",
  "entities": [
    {
      "id": "e0",
      "name": "LangChain",
      "type": "framework",
      "source_node_ids": ["<context_node_id>"]
    },
    {
      "id": "e1",
      "name": "Pinecone",
      "type": "infrastructure",
      "source_node_ids": []
    }
  ],
  "relationships": [
    {"from": "e0", "to": "e1", "type": "integrates_with"},
    {"from": "e0", "to": "e2", "type": "competes_with"}
  ],
  "market_tensions": ["open-source vs managed", "cost vs quality"],
  "key_trends": ["LLM adoption rate", "enterprise readiness concerns"]
}
```

**Entity ID assignment:** IDs (`e0`, `e1`, ...) are assigned by the backend after parsing the LLM response (`f"e{i}"` for each entity in order). The LLM is NOT asked to generate IDs — it returns entities without IDs.

**`source_node_ids` matching:** After ID assignment, for each entity, scan all context_node titles using case-insensitive substring matching (`entity.name.lower() in node["title"].lower()`). All matching node IDs are collected into `source_node_ids`. If no match, the field is an empty list.

**Entity types (10):**
`framework`, `product`, `company`, `technology`, `concept`, `market_segment`, `pain_point`, `research`, `standard`, `regulation`

**Relationship types (8):**
`competes_with`, `integrates_with`, `built_on`, `targets`, `addresses`, `enables`, `regulated_by`, `part_of`

### Token size bounds for ontology slices

Each slice function must produce output within these character limits to avoid exceeding context windows:

- `ontology_for_persona()` → max 400 chars (domain_summary + top 8 entity names + market_tensions)
- `ontology_for_action()` → max 200 chars (domain_summary + top 5 entity names only). Used in `decide_action()` which runs at `tier="low"` with `max_tokens=512`.
- `ontology_for_content()` → max 600 chars (entity name list + relationship summary, one line per rel)

### Error handling

If `build_ontology()` fails (LLM error, JSON parse error, empty response), it logs a warning and returns `None`. The simulation proceeds with `ontology=None`. All injection sites guard against `None`:

```python
if ontology:
    prompt += f"\nEcosystem context:\n{ontology_for_persona(ontology)}"
```

The `sim_ontology` event is only published if ontology is not `None`.

### Data flow

```
tasks.py
  └─ raw_items → context_nodes (existing)
  └─ build_ontology(context_nodes, input_text, provider) → ontology  ← new
  └─ if ontology: publish({"type": "sim_ontology", "data": ontology}) ← new
  └─ run_simulation(..., ontology=ontology)                            ← new param
```

The `sim_ontology` event is published to the Redis stream before `run_simulation()` is called. Since all events go through the same `publish()` → `r.xadd()` path, the Redis stream sequence guarantees `sim_ontology` appears before `sim_start`. Reconnecting clients receive it from the backlog via `XREAD` from their last-seen ID, so no re-emission is needed.

---

## Section 2: Agent Injection

Ontology is sliced into views to avoid token waste. Each view is a compact string injected at the relevant call site.

### Slice functions (in `ontology_builder.py`)

```python
def ontology_for_persona(ontology: dict) -> str:
    # domain_summary + top 8 entity names + market_tensions
    # max 400 chars

def ontology_for_action(ontology: dict) -> str:
    # domain_summary + top 5 entity names only
    # max 200 chars — used in decide_action() (tier="low", max_tokens=512)

def ontology_for_content(ontology: dict) -> str:
    # entity name list + relationship summary (one line per rel)
    # max 600 chars
```

### Injection sites

**Note:** `agent.py:react()` exists in the codebase but has no active call sites in the current simulation execution path. It is not injected here. The active execution path runs through `social_rounds.py`.

**1. `persona_generator.py:generate_persona()`**
Gives the persona generation LLM context about the ecosystem the persona operates in.

```
Ecosystem context:
- Domain: {domain_summary}
- Key players: LangChain (framework), Pinecone (infrastructure), ...
- Market tensions: open-source vs managed, cost vs quality
```

**2. `social_rounds.py:generate_content()`**
Makes posts and comments reference real ecosystem terminology and players. Also covers the "react to idea" reasoning — agents reason about the idea relative to known alternatives and pain points when generating content.

```
Ecosystem context:
- Key players: {entity name list}
- Relationships: LangChain competes with LlamaIndex, RAG enables chatbot products
```

**3. `social_rounds.py:decide_action()`**
Gives agents ecosystem awareness when choosing what action to take on the feed. Uses `ontology_for_action()` (max 200 chars).

```
Ecosystem context:
- Domain: {domain_summary}
- Key players: LangChain, LlamaIndex, Pinecone, ...
```

### Call chain changes

`run_simulation()` receives `ontology: dict | None` and passes it through:

```
run_simulation(ontology)
  └─ collect_personas_for_platform(platform_name, ontology)   ← local wrapper in social_runner.py, must forward
       └─ round_personas(..., ontology) → generate_persona()
  └─ platform_round(..., ontology)
       └─ decide_action(..., ontology)
       └─ generate_content(..., ontology)
```

`collect_personas_for_platform()` is a local async function in `social_runner.py` (lines 55–68 in current code) that wraps `round_personas()`. It must accept and forward the `ontology` parameter.

---

## Section 3: UI Graph Visualization

### Library: `react-force-graph-2d`

D3-based, React-friendly, interactive node/edge support. Bundle size (~60KB gzip after tree-shaking in Vite) is acceptable. Verify with `npm run build --report` before merging.

### Display location

During simulation — below the `sim_analysis` section, above the simulation round feed. A collapsible panel titled "Ecosystem Map". Hidden if `sim_ontology` event was never received.

### Streaming event

```json
{
  "type": "sim_ontology",
  "data": {
    "entities": [...],
    "relationships": [...],
    "domain_summary": "..."
  }
}
```

Frontend receives this event and renders the graph. Only emitted if ontology generation succeeded.

### Visual encoding

**Node colors by type:**

| Type | Color |
|------|-------|
| framework | Blue |
| product | Green |
| company | Orange |
| technology | Purple |
| market_segment | Yellow |
| pain_point | Red |
| research | Teal |
| standard | Gray |
| concept | Lavender |
| regulation | Brown |

**Edge styles by relationship:**

| Relationship | Style |
|-------------|-------|
| competes_with | Red dashed |
| integrates_with | Green solid |
| built_on | Blue solid |
| targets | Orange arrow |
| addresses | Teal arrow |
| enables | Purple arrow |
| regulated_by | Brown dashed |
| part_of | Gray solid |

### Interactions

- Node hover → tooltip (name + type)
- Node click → side panel with entity name, type, and links to source context nodes (via `source_node_ids` → lookup in context_nodes for URL/title). If `source_node_ids` is empty, side panel shows name + type only.
- Drag to reposition nodes
- Legend toggle (show/hide by type)

### Frontend event handling

`DemoPage.tsx` handles `sim_ontology` as a **pre-simulation event** — it arrives before `sim_start` in the Redis stream. The frontend state machine must handle this: `sim_ontology` can be received while the page is still in the "loading" state before `sim_start` fires. Store it in state immediately on receipt regardless of current simulation phase.

### Frontend types

```typescript
interface OntologyEntity {
  id: string;           // "e0", "e1", ...
  name: string;
  type: string;         // one of the 10 entity types
  source_node_ids: string[];
}

interface OntologyRelationship {
  from: string;         // entity id
  to: string;           // entity id
  type: string;         // one of the 8 relationship types
}

interface ContextNode {
  id: string;
  title: string;
  source: string;       // "hackernews", "github", "arxiv", etc.
  abstract: string;
}
```

### New component

`frontend/src/components/OntologyGraph.tsx`

Props:
```typescript
interface OntologyGraphProps {
  entities: OntologyEntity[];
  relationships: OntologyRelationship[];
  domainSummary: string;
  contextNodes: ContextNode[]; // for source link resolution in side panel
}
```

---

## What's Out of Scope

- Agent-to-agent influence relationships — separate feature, to be designed independently after this is shipped.
- Zep integration — not needed at Noosphere's scale (max 30 nodes).
- Dynamic ontology updates during simulation rounds — ontology is fixed at simulation start.

---

## Files to Create / Modify

**Create:**
- `backend/ontology_builder.py` — ontology generation + slice functions + ID assignment
- `frontend/src/components/OntologyGraph.tsx` — force-graph component

**Modify:**
- `backend/tasks.py` — call `build_ontology()`, conditionally publish `sim_ontology`, pass ontology to `run_simulation()`
- `backend/simulation/social_runner.py` — accept `ontology: dict | None`, forward to `round_personas()` and `platform_round()`
- `backend/simulation/social_rounds.py` — accept and forward `ontology` to `generate_persona()`, `decide_action()`, `generate_content()`
- `backend/simulation/persona_generator.py` — accept `ontology` param, inject `ontology_for_persona()` if not None
- `frontend/src/pages/DemoPage.tsx` — handle `sim_ontology` event, store ontology state, pass to `OntologyGraph`
