from __future__ import annotations
import asyncio
import dataclasses
import logging
from collections.abc import AsyncGenerator

from backend.simulation.models import Persona, PlatformState, SocialPost
from backend.simulation.graph_utils import build_adjacency, degree_centrality, build_clusters
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


def _coerce_int(value: object, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _restore_personas(personas_dict: dict) -> dict[str, list[Persona]]:
    """Reconstruct Persona dataclass instances from checkpoint dict."""
    result: dict[str, list[Persona]] = {}
    for platform_name, persona_list in (personas_dict or {}).items():
        if not isinstance(persona_list, list):
            logger.warning("Skipping invalid persona payload for platform %s", platform_name)
            continue
        restored: list[Persona] = []
        for d in persona_list:
            if not isinstance(d, dict):
                logger.warning("Skipping invalid persona entry for platform %s", platform_name)
                continue
            # 'generation' is a @property — must not be passed to constructor
            restored.append(Persona(
                node_id=str(d.get("node_id", "")),
                name=str(d.get("name", "Unknown")),
                role=str(d.get("role", "")),
                age=_coerce_int(d.get("age"), 30),
                seniority=str(d.get("seniority", "")),
                affiliation=str(d.get("affiliation", "")),
                company=str(d.get("company", "")),
                mbti=str(d.get("mbti", "")),
                interests=list(d.get("interests") or []),
                skepticism=_coerce_int(d.get("skepticism"), 5),
                commercial_focus=_coerce_int(d.get("commercial_focus"), 5),
                innovation_openness=_coerce_int(d.get("innovation_openness"), 5),
                source_title=str(d.get("source_title", "")),
                domain_type=str(d.get("domain_type", "")),
                tech_area=list(d.get("tech_area") or []),
                market=list(d.get("market") or []),
                problem_domain=list(d.get("problem_domain") or []),
            ))
        result[platform_name] = restored
    return result


def _restore_platform_states(states_dict: dict) -> dict[str, PlatformState]:
    """Reconstruct PlatformState dataclass instances from checkpoint dict."""
    result: dict[str, PlatformState] = {}
    for platform_name, state_d in (states_dict or {}).items():
        if not isinstance(state_d, dict):
            logger.warning("Skipping invalid platform state payload for %s", platform_name)
            continue
        posts = [
            SocialPost(
                id=str(p.get("id", "")),
                platform=str(p.get("platform", platform_name)),
                author_node_id=str(p.get("author_node_id", "")),
                author_name=str(p.get("author_name", "")),
                content=str(p.get("content", "")),
                action_type=str(p.get("action_type", "post")),
                round_num=_coerce_int(p.get("round_num"), 0),
                upvotes=p.get("upvotes", 0),
                downvotes=p.get("downvotes", 0),
                parent_id=p.get("parent_id"),
                structured_data=p.get("structured_data", {}),
            )
            for p in state_d.get("posts", [])
            if isinstance(p, dict)
        ]
        result[platform_name] = PlatformState(
            platform_name=str(state_d.get("platform_name", platform_name)),
            posts=posts,
            round_num=_coerce_int(state_d.get("round_num"), 0),
            recent_speakers=dict(state_d.get("recent_speakers") or {}),
        )
    return result


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

    adjacency = build_adjacency(edges or [])
    id_to_node = {node["id"]: node for node in nodes if node.get("id")}
    all_node_ids = list(id_to_node.keys())

    clusters = build_clusters(adjacency, all_node_ids, id_to_node)
    clusters = clusters[:max(1, max_agents)]

    cluster_docs_map: dict[str, list[dict]] = {c["id"]: c["nodes"] for c in clusters}

    node_degree = degree_centrality(adjacency, all_node_ids) if edges else {}
    cluster_degree: dict[str, int] = {
        c["id"]: sum(node_degree.get(n.get("id", ""), 0) for n in c["nodes"])
        for c in clusters
    }

    yield {"type": "sim_start", "agent_count": len(clusters)}

    if checkpoint is not None:
        # --- RESUME PATH ---
        platform_personas = _restore_personas(checkpoint["personas"])
        platform_states = _restore_platform_states(checkpoint["platform_states"])
        start_round = checkpoint["last_round"] + 1
        yield {"type": "sim_resume", "from_round": start_round}
    else:
        # --- NORMAL PATH ---
        # Persona generation: one pool per platform, run in parallel
        platform_personas: dict[str, list[Persona]] = {p.name: [] for p in active_platforms}

        async def collect_personas_for_platform(platform_name: str) -> list[tuple[dict, Persona]]:
            results = []
            async for event in round_personas(
                clusters, idea_text,
                platform_name=platform_name,
                provider=provider,
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
            p.name: asyncio.create_task(generate_seed_post(p, idea_text, language, provider=provider, ontology=ontology))
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

        start_round = 1

    # Rounds start_round~num_rounds
    for round_num in range(start_round, num_rounds + 1):
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
                plat, state, plat_personas, cluster_degree, idea_text, rn, language, activation_rate,
                provider=provider,
                cluster_docs_map=cluster_docs_map,
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

        # Emit checkpoint data — intercepted by tasks.py, NOT forwarded to Redis
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
            "analysis_md": "",  # tasks.py fills in the real value when saving
            "ontology": ontology,
            "raw_items": [],    # tasks.py fills in the real value when saving
        }
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
