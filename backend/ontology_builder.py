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

_CHUNK_SIZE = 40

_ENTITY_SYSTEM = (
    "You are a domain knowledge analyst. Extract key entities from the given knowledge nodes "
    "relevant to the idea being evaluated."
)

_REL_SYSTEM = (
    "You are a domain knowledge analyst. Given a list of known entities in a domain ecosystem, "
    "identify the relationships between them and write a domain summary."
)


async def _extract_entities_from_chunk(
    chunk: list[dict],
    input_text: str,
    provider: str,
) -> dict:
    """Extract entities, market_tensions, key_trends from a single chunk of nodes."""
    nodes_text = "\n".join(
        f"- [{n.get('source', '')}] {n.get('title', '')} — {(n.get('abstract') or '')[:150]}"
        for n in chunk
    )
    prompt = (
        f"Idea being evaluated: {input_text[:500]}\n\n"
        f"Knowledge nodes:\n{nodes_text}\n\n"
        f"Extract entities relevant to this idea.\n"
        f"Entity types allowed: {', '.join(ENTITY_TYPES)}\n\n"
        f"Return ONLY valid JSON:\n"
        f'{{"entities": [{{"name": "...", "type": "..."}}], '
        f'"market_tensions": ["..."], "key_trends": ["..."]}}'
    )
    try:
        response = await llm.complete(
            messages=[
                {"role": "system", "content": _ENTITY_SYSTEM},
                {"role": "user", "content": prompt},
            ],
            tier="mid",
            provider=provider,
            max_tokens=1024,
        )
        raw = (response.content or "").strip()
        raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.DOTALL).strip()
        parsed = json.loads(raw) if raw else {}
        return parsed if isinstance(parsed, dict) else {}
    except Exception as exc:
        logger.warning("_extract_entities_from_chunk failed: %s", exc)
        return {}


def _dedup_entities(entities: list[dict]) -> list[dict]:
    """Deduplicate entities by lowercased name, keeping first occurrence."""
    seen: dict[str, dict] = {}
    for e in entities:
        key = (e.get("name") or "").lower().strip()
        if key and key not in seen:
            seen[key] = e
    return list(seen.values())


async def _extract_relationships_and_summary(
    entities: list[dict],
    sample_nodes: list[dict],
    input_text: str,
    provider: str,
) -> tuple[list[dict], str]:
    """Extract relationships between known entities and produce a domain summary."""
    entity_list = ", ".join(
        f"{e.get('name', '')} ({e.get('type', '')})" for e in entities[:60]
    )
    nodes_text = "\n".join(
        f"- [{n.get('source', '')}] {n.get('title', '')} — {(n.get('abstract') or '')[:100]}"
        for n in sample_nodes[:20]
    )
    prompt = (
        f"Idea: {input_text[:400]}\n\n"
        f"Entities in this ecosystem:\n{entity_list}\n\n"
        f"Sample knowledge nodes for context:\n{nodes_text}\n\n"
        f"1. Write a concise domain_summary (1-2 sentences).\n"
        f"2. Identify relationships between the entities.\n"
        f"Relationship types allowed: {', '.join(RELATIONSHIP_TYPES)}\n\n"
        f"Return ONLY valid JSON:\n"
        f'{{"domain_summary": "...", '
        f'"relationships": [{{"from_name": "...", "to_name": "...", "type": "..."}}]}}'
    )
    try:
        response = await llm.complete(
            messages=[
                {"role": "system", "content": _REL_SYSTEM},
                {"role": "user", "content": prompt},
            ],
            tier="mid",
            provider=provider,
            max_tokens=2048,
        )
        raw = (response.content or "").strip()
        raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.DOTALL).strip()
        parsed = json.loads(raw) if raw else {}
        if not isinstance(parsed, dict):
            return [], ""
        domain_summary = str(parsed.get("domain_summary", ""))[:200]
        relationships = parsed.get("relationships", [])
        if not isinstance(relationships, list):
            relationships = []
        return relationships, domain_summary
    except Exception as exc:
        logger.warning("_extract_relationships_and_summary failed: %s", exc)
        return [], ""


async def build_ontology(
    context_nodes: list[dict],
    input_text: str,
    provider: str = "openai",
) -> dict | None:
    """
    Generate a domain ontology from context_nodes using chunked processing.
    Phase 1: Extract entities from each chunk in parallel.
    Phase 2: Merge, deduplicate, then extract relationships + domain_summary.
    Returns ontology dict or None on failure.
    """
    try:
        # Phase 1: Extract entities from all chunks
        chunks = [
            context_nodes[i:i + _CHUNK_SIZE]
            for i in range(0, len(context_nodes), _CHUNK_SIZE)
        ] or [[]]
        import asyncio as _asyncio
        chunk_results = await _asyncio.gather(
            *[_extract_entities_from_chunk(chunk, input_text, provider) for chunk in chunks],
            return_exceptions=True,
        )

        all_entities_raw: list[dict] = []
        all_tensions: list[str] = []
        all_trends: list[str] = []
        for result in chunk_results:
            if isinstance(result, Exception):
                logger.warning("Chunk extraction failed: %s", result)
                continue
            if not isinstance(result, dict):
                logger.warning("Chunk extraction returned non-dict payload: %r", type(result).__name__)
                continue
            raw_ents = result.get("entities", [])
            if not isinstance(raw_ents, list):
                raw_ents = []
            all_entities_raw.extend([
                e for e in raw_ents
                if isinstance(e, dict)
                and isinstance(e.get("name"), str) and e.get("name")
                and isinstance(e.get("type"), str) and e.get("type")
            ])
            raw_tensions = result.get("market_tensions", [])
            if isinstance(raw_tensions, list):
                all_tensions.extend(str(t) for t in raw_tensions if t)
            raw_trends = result.get("key_trends", [])
            if isinstance(raw_trends, list):
                all_trends.extend(str(t) for t in raw_trends if t)

        if not all_entities_raw:
            logger.warning("build_ontology: no entities extracted from any chunk")
            return None

        # Deduplicate and assign IDs
        entities = _dedup_entities(all_entities_raw)
        entities = _assign_ids(entities)

        # Deduplicate tensions and trends (preserve order)
        market_tensions = list(dict.fromkeys(all_tensions))[:5]
        key_trends = list(dict.fromkeys(all_trends))[:5]

        # Phase 2: Extract relationships + domain_summary with full entity list
        raw_relationships, domain_summary = await _extract_relationships_and_summary(
            entities, context_nodes, input_text, provider
        )

        # Resolve from_name/to_name → entity IDs
        name_to_id = {e["name"].lower(): e["id"] for e in entities}
        relationships: list[dict] = []
        for rel in raw_relationships:
            if not isinstance(rel, dict):
                continue
            from_id = name_to_id.get((rel.get("from_name") or "").lower())
            to_id = name_to_id.get((rel.get("to_name") or "").lower())
            if from_id and to_id and rel.get("type") in RELATIONSHIP_TYPES:
                relationships.append({"from": from_id, "to": to_id, "type": rel["type"]})

        entities = _assign_source_node_ids(entities, context_nodes)

        return {
            "domain_summary": domain_summary,
            "entities": entities,
            "relationships": relationships,
            "market_tensions": market_tensions,
            "key_trends": key_trends,
        }
    except Exception as exc:
        logger.warning("build_ontology failed: %s", exc)
        return None


def _assign_ids(entities: list[dict]) -> list[dict]:
    """Assign sequential IDs e0, e1, ... to entities (creates copies, does not mutate)."""
    return [{**e, "id": f"e{i}"} for i, e in enumerate(entities)]


def _assign_source_node_ids(entities: list[dict], context_nodes: list[dict]) -> list[dict]:
    """
    Populate source_node_ids by matching entity name against node title AND abstract.
    Also matches individual significant words from multi-word entity names.
    """
    result = []
    for entity in entities:
        name_lower = (entity.get("name") or "").lower().strip()
        if not name_lower:
            result.append({**entity, "source_node_ids": []})
            continue
        name_words = set(w for w in name_lower.split() if len(w) > 2)
        matched = []
        for n in context_nodes:
            title_lower = n.get("title", "").lower()
            abstract_lower = (n.get("abstract") or "").lower()
            full_text = f"{title_lower} {abstract_lower}"
            # Direct name match in title or abstract
            if name_lower in full_text:
                matched.append(n["id"])
            # Multi-word entity: all significant words appear in the text
            elif len(name_words) >= 2 and name_words.issubset(set(re.findall(r'\b\w+\b', full_text))):
                matched.append(n["id"])
        result.append({**entity, "source_node_ids": matched})
    return result


# ── Slice functions ────────────────────────────────────────────────────────────

def ontology_for_persona(ontology: dict) -> str:
    """max 400 chars — domain_summary + top 8 entity names + market_tensions."""
    domain = ontology.get("domain_summary", "")
    names = ", ".join(
        f"{e.get('name', '')} ({e.get('type', '')})"
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
    names = ", ".join(e.get("name", "") for e in ontology.get("entities", [])[:5])
    text = f"Domain: {domain}\nPlayers: {names}"
    return text[:200]


def ontology_for_content(ontology: dict) -> str:
    """max 600 chars — entity name list + relationship summary."""
    names = ", ".join(
        f"{e.get('name', '')} ({e.get('type', '')})"
        for e in ontology.get("entities", [])
    )
    id_to_name = {e["id"]: e.get("name", "") for e in ontology.get("entities", [])}
    rels = "\n".join(
        f"- {id_to_name.get(r['from'], r['from'])} {r['type']} {id_to_name.get(r['to'], r['to'])}"
        for r in ontology.get("relationships", [])[:10]
    )
    text = f"Players: {names}"
    if rels:
        text += f"\nRelationships:\n{rels}"
    return text[:600]
