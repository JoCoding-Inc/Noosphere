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
        if not isinstance(parsed, dict):
            raise ValueError(f"Expected dict, got {type(parsed).__name__}")

        # Assign IDs backend-side
        raw_entities = parsed.get("entities", [])
        if not isinstance(raw_entities, list):
            raw_entities = []
        # Filter out entities missing required name/type before ID assignment
        raw_entities = [
            e for e in raw_entities
            if isinstance(e, dict)
            and isinstance(e.get("name"), str) and e.get("name")
            and isinstance(e.get("type"), str) and e.get("type")
        ]
        entities = _assign_ids(raw_entities)

        # Resolve relationship from_name/to_name → entity IDs
        name_to_id = {e["name"].lower(): e["id"] for e in entities}
        relationships = []
        for rel in parsed.get("relationships", []):
            if not isinstance(rel, dict):
                continue
            from_id = name_to_id.get((rel.get("from_name") or "").lower())
            to_id = name_to_id.get((rel.get("to_name") or "").lower())
            if from_id and to_id and rel.get("type") in RELATIONSHIP_TYPES:
                relationships.append({"from": from_id, "to": to_id, "type": rel["type"]})

        entities = _assign_source_node_ids(entities, context_nodes)

        return {
            "domain_summary": str(parsed.get("domain_summary", ""))[:200],
            "entities": entities,
            "relationships": relationships,
            "market_tensions": [str(t) for t in parsed.get("market_tensions", [])[:5]],
            "key_trends": [str(t) for t in parsed.get("key_trends", [])[:5]],
        }
    except Exception as exc:
        logger.warning("build_ontology failed: %s", exc)
        return None


def _assign_ids(entities: list[dict]) -> list[dict]:
    """Assign sequential IDs e0, e1, ... to entities (creates copies, does not mutate)."""
    return [{**e, "id": f"e{i}"} for i, e in enumerate(entities)]


def _assign_source_node_ids(entities: list[dict], context_nodes: list[dict]) -> list[dict]:
    """
    Populate source_node_ids via case-insensitive substring match:
    entity.name.lower() in node["title"].lower()
    """
    result = []
    for entity in entities:
        name_lower = (entity.get("name") or "").lower()
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
