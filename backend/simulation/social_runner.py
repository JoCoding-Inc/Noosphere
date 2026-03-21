from __future__ import annotations
import asyncio
import dataclasses
import logging
from collections.abc import AsyncGenerator

from backend.simulation.models import Persona, PlatformState
from backend.simulation.graph_utils import build_adjacency, degree_centrality
from backend.simulation.social_rounds import (
    round_personas, generate_seed_post, platform_round, generate_report
)
from backend.simulation.platforms import PLATFORM_MAP

logger = logging.getLogger(__name__)

PLATFORM_NAMES = ["hackernews", "producthunt", "indiehackers", "reddit_startups", "linkedin"]


def _deduplicate_names(results: list[tuple[dict, "Persona | None"]]) -> None:
    """Assign '(N)' suffix to duplicate persona names within a single platform's result list.

    Mutates both the Persona object and the corresponding sim_persona event dict in-place
    so that the frontend receives consistent names.
    """
    name_counter: dict[str, int] = {}
    for event, persona in results:
        if persona is None:
            continue
        base_name = persona.name
        count = name_counter.get(base_name, 0)
        if count > 0:
            new_name = f"{base_name} ({count + 1})"
            persona.name = new_name
            if event and isinstance(event.get("persona"), dict):
                event["persona"]["name"] = new_name
        name_counter[base_name] = count + 1


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
) -> AsyncGenerator[dict, None]:
    nodes = context_nodes  # alias for rest of function body
    idea_text = input_text  # alias for rest of function body
    if not nodes:
        yield {"type": "sim_error", "message": "No context nodes to simulate"}
        yield {"type": "sim_done"}
        return

    selected_platform_names = platforms or PLATFORM_NAMES
    active_platforms = [PLATFORM_MAP[n] for n in selected_platform_names if n in PLATFORM_MAP]
    if not active_platforms:
        yield {"type": "sim_error", "message": "No valid platforms specified"}
        yield {"type": "sim_done"}
        return

    nodes = nodes[:max(1, min(150, max_agents))]
    adjacency = build_adjacency(edges or [])
    id_to_node = {node["id"]: node for node in nodes if node.get("id")}
    degree = degree_centrality(adjacency, list(id_to_node.keys())) if edges else None

    yield {"type": "sim_start", "agent_count": len(nodes)}

    # Persona generation: one pool per platform, run in parallel
    platform_personas: dict[str, list[Persona]] = {p.name: [] for p in active_platforms}

    async def collect_personas_for_platform(platform_name: str) -> list[tuple[dict, Persona]]:
        results = []
        async for event in round_personas(
            nodes, idea_text,
            adjacency=adjacency, id_to_node=id_to_node,
            platform_name=platform_name,
            provider=provider,
            ontology=ontology,
        ):
            persona = event.pop("_persona", None)
            if persona is not None:
                results.append((event, persona))
            else:
                results.append((event, None))
        _deduplicate_names(results)
        return results

    persona_tasks = {
        p.name: asyncio.create_task(collect_personas_for_platform(p.name))
        for p in active_platforms
    }
    for platform_name, task in persona_tasks.items():
        try:
            entries = await task
            for event, persona in entries:
                if persona is not None:
                    platform_personas[platform_name].append(persona)
                yield event
        except Exception as exc:
            logger.warning("Persona generation failed for platform %s: %s", platform_name, exc)

    if not any(platform_personas.values()):
        yield {"type": "sim_error", "message": "Persona generation failed for all platforms"}
        yield {"type": "sim_done"}
        return

    # Round 0: seed posts for each platform (parallel)
    platform_states: dict[str, PlatformState] = {}
    seed_tasks = {
        p.name: asyncio.create_task(generate_seed_post(p, idea_text, language, provider=provider))
        for p in active_platforms
    }
    for name, task in seed_tasks.items():
        try:
            seed_post = await task
            state = PlatformState(platform_name=name, posts=[seed_post], round_num=0)
            platform_states[name] = state
            yield {"type": "sim_platform_post", "platform": name,
                   "post": dataclasses.asdict(seed_post)}
        except Exception as exc:
            logger.warning("Seed post failed for %s: %s", name, exc)

    if not platform_states:
        yield {"type": "sim_error", "message": "All platforms failed to initialize"}
        yield {"type": "sim_done"}
        return

    # Rounds 1~num_rounds
    for round_num in range(1, num_rounds + 1):
        async def run_platform_round(plat, rn=round_num):
            events_out = []
            state = platform_states.get(plat.name)
            if state is None:
                return events_out
            plat_personas = platform_personas.get(plat.name) or []
            if not plat_personas:
                logger.warning("No personas for platform %s, skipping round %d", plat.name, rn)
                return events_out
            async for event in platform_round(
                plat, state, plat_personas, degree, idea_text, rn, language, activation_rate,
                provider=provider,
                ontology=ontology,
            ):
                events_out.append(event)
            return events_out

        results = await asyncio.gather(
            *[run_platform_round(p) for p in active_platforms],
            return_exceptions=True,
        )

        round_summary_stats: dict[str, dict] = {}
        for result in results:
            if isinstance(result, Exception):
                logger.warning("Platform round failed: %s", result)
                continue
            for event in result:
                if event["type"] == "__platform_round_done__":
                    round_summary_stats[event["platform"]] = event["stats"]
                else:
                    yield event

        failed = sum(1 for r in results if isinstance(r, Exception))
        if 0 < failed and failed * 2 <= len(active_platforms):
            yield {"type": "sim_warning",
                   "message": f"{failed} platform(s) failed this round but simulation continues"}
        if failed * 2 > len(active_platforms):
            yield {"type": "sim_error",
                   "message": f"Too many platforms failed ({failed}/{len(active_platforms)})"}
            yield {"type": "sim_done"}
            return

        yield {
            "type": "sim_round_summary",
            "round_num": round_num,
            "platform_summaries": round_summary_stats,
        }

    # Final report
    try:
        report_json, report_md = await generate_report(
            list(platform_states.values()), idea_text, domain, language, provider=provider
        )
    except Exception as exc:
        logger.error("Report generation failed: %s", exc)
        report_json = {}
        report_md = "## Report\n\nGeneration failed."

    yield {
        "type": "sim_report",
        "data": {
            "report_json": report_json,
            "markdown": report_md,
            "platform_states": {
                state.platform_name: [
                    {
                        "id": p.id,
                        "platform": state.platform_name,
                        "author_node_id": p.author_node_id,
                        "author_name": p.author_name,
                        "content": p.content,
                        "action_type": p.action_type,
                        "round_num": p.round_num,
                        "upvotes": p.upvotes,
                        "downvotes": p.downvotes,
                        "parent_id": p.parent_id,
                    }
                    for p in state.posts
                ]
                for state in platform_states.values()
            },
            "personas": {
                name: [
                    {
                        "node_id": p.node_id, "name": p.name, "role": p.role,
                        "age": p.age, "generation": p.generation,
                        "seniority": p.seniority, "affiliation": p.affiliation,
                        "company": p.company, "mbti": p.mbti,
                        "interests": p.interests,
                        "skepticism": p.skepticism,
                        "commercial_focus": p.commercial_focus,
                        "innovation_openness": p.innovation_openness,
                    }
                    for p in personas_list
                ]
                for name, personas_list in platform_personas.items()
            } if 'platform_personas' in dir() else {},
        },
    }
    yield {"type": "sim_done"}
