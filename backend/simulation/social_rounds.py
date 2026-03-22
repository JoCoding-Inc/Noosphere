from __future__ import annotations
import asyncio
import dataclasses
import logging
import random
import uuid
from collections.abc import AsyncGenerator

from backend.simulation.models import Persona, SocialPost, PlatformState
from backend.simulation.persona_generator import generate_persona
from backend.simulation.platforms.base import AbstractPlatform, AgentAction
from backend import llm
from backend.llm import LLMToolRequired

logger = logging.getLogger(__name__)


def _to_openai_tool(tool: dict) -> dict:
    return {
        "type": "function",
        "function": {
            "name": tool["name"],
            "description": tool.get("description", ""),
            "parameters": tool["input_schema"],
        }
    }


def _build_prior_knowledge(
    cluster_id: str,
    cluster_docs_map: dict,
    persona,
    top_k: int = 5,
) -> str:
    """Build prior knowledge text from the agent's cluster documents,
    ranked by relevance to the persona's taxonomy fields."""
    docs = cluster_docs_map.get(cluster_id, [])
    if not docs:
        return ""

    def relevance_score(doc):
        score = 0
        if persona.domain_type and doc.get("_domain_type") == persona.domain_type:
            score += 1
        score += len(set(persona.tech_area) & set(doc.get("_tech_area") or []))
        score += len(set(persona.market) & set(doc.get("_market") or []))
        score += len(set(persona.problem_domain) & set(doc.get("_problem_domain") or []))
        return score

    ranked = sorted(docs, key=relevance_score, reverse=True)

    parts: list[str] = []
    for doc in ranked[:top_k]:
        title = doc.get("title", "").strip()
        source = doc.get("source", "").strip()
        abstract = (doc.get("abstract") or "").strip()
        line = f"  [{source}] {title}"
        if abstract:
            line += f"\n    {abstract}"
        parts.append(line)
    return "\n".join(parts)


# ── 에이전트 선정 ─────────────────────────────────────────────────────────────

def select_active_agents(
    personas: list[Persona],
    degree: dict[str, int] | None,
    activation_rate: float = 0.25,
    recent_speakers: dict[str, int] | None = None,
    current_round: int = 0,
) -> list[Persona]:
    """Degree-weighted random selection with cross-round cooldown.

    recent_speakers: node_id → last round they produced content (comment/reply).
    Agents who spoke in the previous round get weight * 0.1.
    Agents who spoke two rounds ago get weight * 0.5.
    Always returns at least 1 agent even if all are on cooldown.
    """
    k = max(1, round(len(personas) * activation_rate))

    def _base_weight(p: Persona) -> float:
        base = float(max(1, degree.get(p.node_id, 0)) if degree else 1.0)
        if recent_speakers is None:
            return base
        last = recent_speakers.get(p.node_id, -99)
        if last == current_round - 1:
            return base * 0.1
        if last == current_round - 2:
            return base * 0.5
        return base

    # uniform fallback when degree is None and no cooldown
    if degree is None and recent_speakers is None:
        return random.sample(personas, min(k, len(personas)))

    weights = [_base_weight(p) for p in personas]
    selected: list[Persona] = []
    pool = list(zip(personas, weights))
    while len(selected) < k and pool:
        total = sum(w for _, w in pool)
        r = random.uniform(0, total)
        cumulative = 0.0
        for i, (persona, w) in enumerate(pool):
            cumulative += w
            if r <= cumulative:
                selected.append(persona)
                pool.pop(i)
                break
    return selected


# ── 씨드 포스트 생성 ──────────────────────────────────────────────────────────

async def generate_seed_post(
    platform: AbstractPlatform,
    idea_text: str,
    language: str = "English",
    provider: str = "openai",
    ontology: dict | None = None,
) -> SocialPost:
    """Generate the initial post for a platform that kicks off discussion."""
    tool = _to_openai_tool(platform.seed_tool())
    tool_name = tool["function"]["name"]
    context_lines = [
        f"Introduce the following idea on {platform.name}. "
        f"Match the platform's tone and style exactly. Write in {language}.\n",
        f"Idea: {idea_text}",
    ]
    if ontology:
        tensions = ontology.get("market_tensions", [])
        trends = ontology.get("key_trends", [])
        if tensions:
            context_lines.append(f"\nKey market tensions in this space: {'; '.join(tensions[:3])}")
        if trends:
            context_lines.append(f"Key trends shaping this space: {'; '.join(trends[:3])}")
    prompt = "\n".join(context_lines)
    structured_data: dict = {}
    content = f"[{platform.name}] Introducing: {idea_text[:200]}"
    try:
        response = await llm.complete(
            messages=[
                {"role": "system", "content": platform.system_prompt},
                {"role": "user", "content": prompt},
            ],
            tier="mid",
            provider=provider,
            max_tokens=2048,
            tools=[tool],
            tool_choice=tool_name,
        )
        structured_data = response.tool_args or {}
        content = platform.extract_seed_content(structured_data)
    except LLMToolRequired:
        raise
    except Exception as exc:
        logger.warning("Seed post generation failed for %s: %s", platform.name, exc)
    return SocialPost(
        id=f"__seed__{platform.name}",
        platform=platform.name,
        author_node_id="__seed__",
        author_name="Noosphere",
        content=content,
        action_type="post",
        round_num=0,
        structured_data=structured_data,
    )


# ── 액션 결정 ─────────────────────────────────────────────────────────────────

_ACTION_SYSTEM = "You are deciding what action to take on a social platform. Stay in character as the given persona."

_DECIDE_ACTION_TOOL = {
    "type": "function",
    "function": {
        "name": "decide_action",
        "description": "Choose one action to take on the platform feed.",
        "parameters": {
            "type": "object",
            "properties": {
                "action_type": {
                    "type": "string",
                    "description": "The action to take. Must be one of the allowed actions listed.",
                },
                "target_post_id": {
                    "type": ["string", "null"],
                    "description": "Post ID to target (for replies/votes), or null for a new top-level post.",
                },
            },
            "required": ["action_type", "target_post_id"],
        },
    },
}


async def decide_action(
    persona: Persona,
    platform: AbstractPlatform,
    feed_text: str,
    language: str = "English",
    provider: str = "openai",
    ontology: dict | None = None,
) -> AgentAction:
    """LLM call 1: decide action_type and target_post_id."""
    del ontology
    allowed = platform.get_allowed_actions(persona)
    prompt = (
        f"Platform: {platform.name}\n"
        f"Your persona: {persona.name}, {persona.role} at {persona.company} "
        f"({persona.seniority}, {persona.affiliation}, age {persona.age})\n"
        f"Bias: {persona.bias_description()}\n"
        f"Allowed actions: {', '.join(allowed)}\n\n"
        f"{feed_text}\n\n"
        f"Choose one action from {allowed}. "
        f"For vote/react actions, pick a target_post_id from the feed. "
        f"For new content, target_post_id can be null (new top-level) or a post id (reply)."
    )
    try:
        response = await llm.complete(
            messages=[
                {"role": "system", "content": _ACTION_SYSTEM},
                {"role": "user", "content": prompt},
            ],
            tier="low",
            provider=provider,
            max_tokens=512,
            tools=[_DECIDE_ACTION_TOOL],
            tool_choice="decide_action",
        )
        data = response.tool_args or {}
        action_type = data.get("action_type", allowed[0])
        if action_type not in allowed:
            action_type = allowed[0]
        target = data.get("target_post_id") or None
        return AgentAction(action_type=action_type, target_post_id=target)
    except LLMToolRequired:
        raise
    except Exception as exc:
        logger.warning("decide_action failed for %s on %s: %s", persona.node_id, platform.name, exc)
        return AgentAction(action_type=allowed[0], target_post_id=f"__seed__{platform.name}")


# ── 콘텐츠 생성 ───────────────────────────────────────────────────────────────

async def generate_content(
    persona: Persona,
    action: AgentAction,
    platform: AbstractPlatform,
    feed_text: str,
    idea_text: str,
    language: str = "English",
    provider: str = "openai",
    cluster_docs_map: dict | None = None,
    ontology: dict | None = None,
) -> tuple[str, dict]:
    """LLM call 2: generate post/comment text. Returns (content_str, structured_data)."""
    del ontology
    tool = _to_openai_tool(platform.content_tool(action.action_type))
    tool_name = tool["function"]["name"]
    prior_knowledge = ""
    if cluster_docs_map is not None:
        prior_knowledge = _build_prior_knowledge(persona.node_id, cluster_docs_map, persona)
    prompt = (
        f"Platform: {platform.name}\n"
        f"You are {persona.name}, {persona.role} at {persona.company} "
        f"({persona.seniority}, {persona.affiliation}, age {persona.age}, {persona.generation}).\n"
        f"Interests: {', '.join(persona.interests[:5])}\n"
        f"Bias: {persona.bias_description()}\n"
        f"Action: {action.action_type}"
        + (f" (replying to post {action.target_post_id})" if action.target_post_id else "") + "\n\n"
        f"Idea being discussed: {idea_text}\n\n"
        + (f"Your domain knowledge:\n{prior_knowledge}\n\n" if prior_knowledge else "")
        + f"{feed_text}\n\n"
        f"Write your {action.action_type} in {language}. Be authentic to your persona and the platform style."
    )
    try:
        response = await llm.complete(
            messages=[
                {"role": "system", "content": platform.system_prompt},
                {"role": "user", "content": prompt},
            ],
            tier="mid",
            provider=provider,
            max_tokens=2048,
            tools=[tool],
            tool_choice=tool_name,
        )
        structured_data = response.tool_args or {}
        content = platform.extract_content(action.action_type, structured_data)
        return content, structured_data
    except LLMToolRequired:
        raise
    except Exception as exc:
        logger.warning("generate_content failed for %s: %s", persona.node_id, exc)
        return f"[{persona.name}] Interesting idea.", {}


# ── 페르소나 생성 라운드 ──────────────────────────────────────────────────────

async def round_personas(
    clusters: list[dict],
    idea_text: str,
    concurrency: int = 4,
    platform_name: str = "",
    provider: str = "openai",
) -> AsyncGenerator[dict, None]:
    """Generate personas for all clusters for a specific platform. Yields sim_persona events."""
    sem = asyncio.Semaphore(concurrency)
    queue: asyncio.Queue = asyncio.Queue()

    async def process_one(cluster: dict) -> None:
        async with sem:
            try:
                persona = await generate_persona(
                    cluster,
                    idea_text=idea_text,
                    platform_name=platform_name,
                    provider=provider,
                )
                await queue.put({
                    "type": "sim_persona",
                    "node_id": cluster.get("id", ""),
                    "platform": platform_name,
                    "persona": {
                        "name": persona.name,
                        "role": persona.role,
                        "age": persona.age,
                        "generation": persona.generation,
                        "seniority": persona.seniority,
                        "affiliation": persona.affiliation,
                        "company": persona.company,
                        "mbti": persona.mbti,
                        "interests": persona.interests,
                        "skepticism": persona.skepticism,
                        "commercial_focus": persona.commercial_focus,
                        "innovation_openness": persona.innovation_openness,
                        "source_title": persona.source_title,
                    },
                    "_persona": persona,
                })
            except Exception as exc:
                logger.warning("Persona gen failed for %s: %s", cluster.get("id", "?"), exc)
            finally:
                await queue.put(None)

    tasks = [asyncio.create_task(process_one(c)) for c in clusters]
    try:
        remaining = len(tasks)
        while remaining > 0:
            item = await queue.get()
            if item is None:
                remaining -= 1
            else:
                yield item
    finally:
        for t in tasks:
            t.cancel()


# ── 플랫폼 라운드 ─────────────────────────────────────────────────────────────

async def platform_round(
    platform: AbstractPlatform,
    state: PlatformState,
    personas: list[Persona],
    degree: dict[str, int] | None,
    idea_text: str,
    round_num: int,
    language: str = "English",
    activation_rate: float = 0.25,
    provider: str = "openai",
    cluster_docs_map: dict | None = None,
) -> AsyncGenerator[dict, None]:
    """Run one round for a single platform. Yields streaming events."""
    active = select_active_agents(
        personas, degree, activation_rate,
        recent_speakers=state.recent_speakers,
        current_round=round_num,
    )
    state.round_num = round_num
    round_stats = {"active_agents": len(active), "new_posts": 0, "new_comments": 0, "new_votes": 0}

    for persona in active:
        feed_text = platform.build_feed(state)
        action = await decide_action(persona, platform, feed_text, language, provider=provider)

        if platform.requires_content(action.action_type):
            content, structured_data = await generate_content(
                persona, action, platform, feed_text, idea_text, language,
                provider=provider,
                cluster_docs_map=cluster_docs_map,
            )
            post = SocialPost(
                id=str(uuid.uuid4()),
                platform=platform.name,
                author_node_id=persona.node_id,
                author_name=persona.name,
                content=content,
                action_type=action.action_type,
                round_num=round_num,
                parent_id=action.target_post_id,
                structured_data=structured_data,
            )
            state.posts.append(post)
            state.recent_speakers[persona.node_id] = round_num
            if action.target_post_id:
                round_stats["new_comments"] += 1
            else:
                round_stats["new_posts"] += 1
            yield {"type": "sim_platform_post", "platform": platform.name,
                   "post": dataclasses.asdict(post)}
        else:
            # Vote/react action
            target_id = action.target_post_id or f"__seed__{platform.name}"
            updated = platform.update_vote_counts(state, target_id, action.action_type)
            round_stats["new_votes"] += 1
            yield {
                "type": "sim_platform_reaction",
                "platform": platform.name,
                "post_id": target_id,
                "reaction_type": action.action_type,
                "actor_name": persona.name,
                "new_upvotes": updated.upvotes if updated else 0,
                "new_downvotes": updated.downvotes if updated else 0,
            }

    yield {
        "type": "__platform_round_done__",
        "platform": platform.name,
        "round_num": round_num,
        "stats": round_stats,
    }


# ── 리포트 생성 ───────────────────────────────────────────────────────────────

_REPORT_SYSTEM = "You are an expert product analyst synthesizing a multi-platform social simulation."

_REPORT_TOOL = {
    "type": "function",
    "function": {
        "name": "create_report",
        "description": "Create a structured product validation report from simulation data.",
        "parameters": {
            "type": "object",
            "properties": {
                "verdict": {
                    "type": "string",
                    "enum": ["positive", "mixed", "skeptical", "negative"],
                    "description": "Overall market reception verdict",
                },
                "evidence_count": {
                    "type": "integer",
                    "description": "Total posts and comments across all platforms",
                },
                "segments": {
                    "type": "array",
                    "description": "Include all 5 segment types",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {
                                "type": "string",
                                "enum": ["developer", "investor", "early_adopter", "skeptic", "pm"],
                            },
                            "sentiment": {
                                "type": "string",
                                "enum": ["positive", "neutral", "negative"],
                            },
                            "summary": {"type": "string", "description": "2-3 sentence summary of this segment's reaction"},
                            "key_quotes": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "1-2 representative quotes from this segment",
                            },
                        },
                        "required": ["name", "sentiment", "summary", "key_quotes"],
                    },
                    "minItems": 5,
                    "maxItems": 5,
                },
                "criticism_clusters": {
                    "type": "array",
                    "description": "Top 3-5 recurring objections or concerns",
                    "items": {
                        "type": "object",
                        "properties": {
                            "theme": {"type": "string", "description": "Short theme label (e.g. 'pricing concerns')"},
                            "count": {"type": "integer", "description": "How many personas raised this"},
                            "examples": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "1-2 example quotes",
                            },
                        },
                        "required": ["theme", "count", "examples"],
                    },
                    "minItems": 3,
                    "maxItems": 5,
                },
                "improvements": {
                    "type": "array",
                    "description": "Top 3-5 actionable improvement suggestions",
                    "items": {
                        "type": "object",
                        "properties": {
                            "suggestion": {"type": "string", "description": "Concrete improvement suggestion"},
                            "frequency": {"type": "integer", "description": "How many personas implied this"},
                        },
                        "required": ["suggestion", "frequency"],
                    },
                    "minItems": 3,
                    "maxItems": 5,
                },
            },
            "required": ["verdict", "evidence_count", "segments", "criticism_clusters", "improvements"],
        },
    },
}


async def generate_report(
    platform_states: list,
    idea_text: str,
    domain: str,
    language: str = "English",
    provider: str = "openai",
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
        + f"\n\nInstructions:\n"
        f"- verdict: overall market reception\n"
        f"- segments: include all 5 segment types even if some have neutral sentiment\n"
        f"- criticism_clusters: top 3-5 recurring objections\n"
        f"- improvements: top 3-5 actionable suggestions\n"
        f"- All text fields must be in {language}"
    )

    report_json: dict = {}
    try:
        response = await llm.complete(
            messages=[
                {"role": "system", "content": _REPORT_SYSTEM},
                {"role": "user", "content": prompt},
            ],
            tier="high",
            provider=provider,
            max_tokens=16384,
            timeout=300.0,
            tools=[_REPORT_TOOL],
            tool_choice="create_report",
        )
        report_json = response.tool_args or {}
    except LLMToolRequired:
        raise
    except Exception as exc:
        logger.warning("Report generation failed: %s", exc)

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
