from __future__ import annotations
import asyncio
import dataclasses
import logging
import random
import uuid
from collections.abc import AsyncGenerator

from backend.simulation.models import Persona, SocialPost, PlatformState
from backend.simulation.persona_generator import generate_persona, sample_persona_names
from backend.simulation.platforms.base import AbstractPlatform, AgentAction
from backend.simulation.taxonomy import coerce_string_list as _coerce_string_list
from backend import llm
from backend.llm import LLMToolRequired

logger = logging.getLogger(__name__)


def _normalized_value(value: object) -> str:
    """Return lowercased stripped string, or empty string if not a non-empty str."""
    return str(value).strip().lower() if isinstance(value, str) and value.strip() else ""


def _normalized_list(value: object) -> set[str]:
    """Return a lowercase set of items from a string or list using taxonomy coerce_string_list."""
    return {item.lower() for item in _coerce_string_list(value)}


# ── Report rendering constants ────────────────────────────────────────────────

_VERDICT_EMOJI: dict[str, str] = {
    "positive": "✅",
    "mixed": "⚖️",
    "skeptical": "🤔",
    "negative": "❌",
}
_SENTIMENT_ICON: dict[str, str] = {"positive": "👍", "neutral": "😐", "negative": "👎"}


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
    persona: Persona,
    top_k: int = 5,
) -> str:
    """Build prior knowledge text from the agent's cluster documents,
    ranked by relevance to the persona's taxonomy fields."""
    docs = cluster_docs_map.get(cluster_id, [])
    if not docs:
        return ""

    def relevance_score(doc):
        score = 0
        if (
            _normalized_value(persona.domain_type)
            and _normalized_value(doc.get("_domain_type")) == _normalized_value(persona.domain_type)
        ):
            score += 1
        score += len(_normalized_list(persona.tech_area) & _normalized_list(doc.get("_tech_area")))
        score += len(_normalized_list(persona.market) & _normalized_list(doc.get("_market")))
        score += len(_normalized_list(persona.problem_domain) & _normalized_list(doc.get("_problem_domain")))
        # keywords/entities: 구체적 내용 기반 유사도 (분류 필드보다 가중치 높음)
        score += len(_normalized_list(persona.interests) & _normalized_list(doc.get("_keywords"))) * 2
        score += len(_normalized_list(persona.interests) & _normalized_list(doc.get("_entities"))) * 2
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
    activation_rate: float = 0.25,
    recent_speakers: dict[str, int] | None = None,
    current_round: int = 0,
    posts: list[SocialPost] | None = None,
) -> list[Persona]:
    """70% new agents (3+ rounds idle, random) + 30% returning (replied-to first).

    recent_speakers: node_id → last round they produced content.
    posts: all platform posts used to find which returning agents received replies.
    Always returns at least 1 agent.
    """
    k = max(1, round(len(personas) * activation_rate))
    k_new = round(k * 0.7)
    k_return = k - k_new

    speakers = recent_speakers or {}

    # New pool: agents idle for 3+ rounds (never-spoken agents always qualify)
    new_pool = [
        p for p in personas
        if current_round - speakers.get(p.node_id, -99) >= 3
    ]
    random.shuffle(new_pool)
    selected_new = new_pool[:k_new]
    selected_ids = {p.node_id for p in selected_new}

    # NOTE: no surplus transfer — new-agent shortfall does NOT bleed into returning pool.
    # This prevents the same agents from bypassing the cooldown.

    # Returning pool: previously spoken, not already selected
    returning_pool = [
        p for p in personas
        if p.node_id not in selected_ids and p.node_id in speakers
    ]

    # Prioritize returning agents whose posts received replies
    if posts:
        post_author: dict[str, str] = {post.id: post.author_node_id for post in posts}
        replied_authors: set[str] = {
            post_author[post.parent_id]
            for post in posts
            if post.parent_id and post.parent_id in post_author
        }
        prioritized = [p for p in returning_pool if p.node_id in replied_authors]
        fallback = [p for p in returning_pool if p.node_id not in replied_authors]
        random.shuffle(prioritized)
        random.shuffle(fallback)
        ordered_returning = prioritized + fallback
    else:
        random.shuffle(returning_pool)
        ordered_returning = returning_pool

    selected_return = ordered_returning[:k_return]
    selected = selected_new + selected_return

    # Fill remaining slots from leftover new pool (cooldown-eligible agents not yet picked)
    if len(selected) < k:
        leftover_ids = {p.node_id for p in selected}
        extra = [p for p in new_pool[k_new:] if p.node_id not in leftover_ids]
        selected += extra[:k - len(selected)]

    return selected


# ── 씨드 포스트 생성 ──────────────────────────────────────────────────────────

async def generate_seed_post(
    platform: AbstractPlatform,
    idea_text: str,
    language: str = "English",
) -> SocialPost:
    """Generate the initial post for a platform that kicks off discussion."""
    tool = _to_openai_tool(platform.seed_tool())
    tool_name = tool["function"]["name"]
    context_lines = [
        f"Introduce the following idea on {platform.name}. "
        f"Match the platform's tone and style exactly. Write in {language}.\n",
        f"Idea: {idea_text}",
    ]
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
) -> AgentAction:
    """LLM call 1: decide action_type and target_post_id."""
    allowed = platform.get_allowed_actions(persona)
    content_actions = [a for a in allowed if a not in platform.no_content_actions]
    content_bias = (
        f"IMPORTANT: You MUST choose a content-writing action ({', '.join(content_actions)}) "
        f"unless there is truly nothing worth saying. Passive actions like upvote/flag should be rare exceptions. "
        f"Aim to write substantive content at least 80% of the time.\n"
    ) if content_actions else ""
    prompt = (
        f"Platform: {platform.name}\n"
        f"Your persona: {persona.name}, {persona.role} at {persona.company} "
        f"({persona.seniority}, {persona.affiliation}, age {persona.age})\n"
        f"Bias: {persona.bias_description()}\n"
        + (f"Emotional state: {persona.emotional_state}\n" if persona.emotional_state else "")
        + f"Note: You are a community member reacting to someone else's product idea. You are NOT the creator.\n"
        f"Allowed actions: {', '.join(allowed)}\n\n"
        f"{content_bias}"
        f"{feed_text}\n\n"
        f"Choose one action from {allowed}. "
        f"For vote/react actions, pick a target_post_id from the feed. "
        f"For new content, target_post_id can be null (new top-level) or a post id (reply). "
        f"If you see a comment you strongly agree or disagree with, reply to that comment's ID directly."
    )
    try:
        response = await llm.complete(
            messages=[
                {"role": "system", "content": _ACTION_SYSTEM},
                {"role": "user", "content": prompt},
            ],
            tier="low",
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
    cluster_docs_map: dict | None = None,
    persona_history: list | None = None,
) -> tuple[str, dict]:
    """LLM call 2: generate post/comment text. Returns (content_str, structured_data)."""
    tool = _to_openai_tool(platform.content_tool(action.action_type))
    tool_name = tool["function"]["name"]
    prior_knowledge = ""
    if cluster_docs_map is not None:
        prior_knowledge = _build_prior_knowledge(persona.node_id, cluster_docs_map, persona)
    history_section = ""
    if persona_history:
        lines = [
            f'- [Round {p.round_num}] "{p.content[:200].replace(chr(10), " ")}"'
            for p in persona_history
        ]
        history_section = (
            "Your previous comments in this discussion (do NOT repeat the same points — "
            "build on, evolve, or take a new angle instead):\n"
            + "\n".join(lines) + "\n\n"
        )
    prompt = (
        f"Platform: {platform.name}\n"
        f"You are {persona.name}, {persona.role} at {persona.company} "
        f"({persona.seniority}, {persona.affiliation}, age {persona.age}, {persona.generation}).\n"
        f"Interests: {', '.join(persona.interests[:5])}\n"
        f"Bias: {persona.bias_description()}\n"
        + (f"Emotional state: {persona.emotional_state}\n" if persona.emotional_state else "")
        + f"Action: {action.action_type}"
        + (f" (replying to post {action.target_post_id})" if action.target_post_id else "") + "\n\n"
        f"IMPORTANT: You are NOT the creator of the idea below. You are a third-party community member reacting to someone else's product pitch.\n"
        f"Someone else's idea being discussed: {idea_text}\n\n"
        + (f"Your domain knowledge:\n{prior_knowledge}\n\n" if prior_knowledge else "")
        + history_section
        + f"{feed_text}\n\n"
        f"Write your {action.action_type} in {language}. Be authentic to your persona and the platform style. Do NOT claim to be the founder or creator of this idea. "
        f"If replying to a comment, directly address what that person said — agree, push back, or add nuance. "
        f"Even when posting independently, you may reference or react to opinions already visible in the feed."
    )
    try:
        response = await llm.complete(
            messages=[
                {"role": "system", "content": platform.system_prompt},
                {"role": "user", "content": prompt},
            ],
            tier="mid",
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
) -> AsyncGenerator[dict, None]:
    """Generate personas for all clusters for a specific platform. Yields sim_persona events."""
    sem = asyncio.Semaphore(concurrency)
    queue: asyncio.Queue = asyncio.Queue()
    assigned_names = sample_persona_names(len(clusters))

    async def process_one(cluster: dict, assigned_name: str) -> None:
        async with sem:
            try:
                persona = await generate_persona(
                    cluster,
                    idea_text=idea_text,
                    platform_name=platform_name,
                    assigned_name=assigned_name,
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
                        "jtbd": persona.jtbd,
                        "cognitive_pattern": persona.cognitive_pattern,
                        "emotional_state": persona.emotional_state,
                    },
                    "_persona": persona,
                })
            except Exception as exc:
                logger.warning("Persona gen failed for %s: %s", cluster.get("id", "?"), exc)
            finally:
                await queue.put(None)

    tasks = [asyncio.create_task(process_one(c, assigned_names[i])) for i, c in enumerate(clusters)]
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
    idea_text: str,
    round_num: int,
    language: str = "English",
    activation_rate: float = 0.25,
    cluster_docs_map: dict | None = None,
) -> AsyncGenerator[dict, None]:
    """Run one round for a single platform. Yields streaming events."""
    active = select_active_agents(
        personas, activation_rate,
        recent_speakers=state.recent_speakers,
        current_round=round_num,
        posts=state.posts,
    )
    state.round_num = round_num
    round_stats = {"active_agents": len(active), "new_posts": 0, "new_comments": 0, "new_votes": 0}

    for persona in active:
        feed_text = platform.build_feed(state)
        persona_history = [p for p in state.posts if p.author_node_id == persona.node_id]
        action = await decide_action(persona, platform, feed_text, language)

        # If the agent chose a vote/reaction action, apply it first
        if not platform.requires_content(action.action_type) and action.target_post_id:
            updated = platform.update_vote_counts(state, action.target_post_id, action.action_type)
            round_stats["new_votes"] += 1
            yield {
                "type": "sim_platform_reaction",
                "platform": platform.name,
                "post_id": action.target_post_id,
                "reaction_type": action.action_type,
                "actor_name": persona.name,
                "new_upvotes": updated.upvotes if updated else 0,
                "new_downvotes": updated.downvotes if updated else 0,
            }

        # Always also generate a content post/comment
        allowed = platform.get_allowed_actions(persona)
        content_actions = [a for a in allowed if platform.requires_content(a)]
        if content_actions:
            content_action = action if platform.requires_content(action.action_type) else \
                AgentAction(action_type=content_actions[0], target_post_id=action.target_post_id)
            content, structured_data = await generate_content(
                persona, content_action, platform, feed_text, idea_text, language,
                cluster_docs_map=cluster_docs_map,
                persona_history=persona_history or None,
            )
            post = SocialPost(
                id=str(uuid.uuid4()),
                platform=platform.name,
                author_node_id=persona.node_id,
                author_name=persona.name,
                content=content,
                action_type=content_action.action_type,
                round_num=round_num,
                parent_id=content_action.target_post_id,
                structured_data=structured_data,
                sentiment=structured_data.get("sentiment", ""),
            )
            state.add_post(post)
            state.recent_speakers[persona.node_id] = round_num
            if content_action.target_post_id:
                round_stats["new_comments"] += 1
            else:
                round_stats["new_posts"] += 1
            yield {"type": "sim_platform_post", "platform": platform.name,
                   "post": dataclasses.asdict(post)}

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
        f"Product: {idea_text}\n\n"
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


_REPORT_I18N: dict[str, dict[str, str]] = {
    "Korean": {
        "overall_verdict": "종합 평가",
        "based_on": "{n}개의 시뮬레이션 인터랙션 기반",
        "segment_reactions": "세그먼트별 반응",
        "criticism_patterns": "비판 패턴",
        "improvement_suggestions": "개선 제안",
        "mentions": "{n}회 언급",
        "seg_developer": "개발자",
        "seg_investor": "투자자",
        "seg_early_adopter": "얼리 어답터",
        "seg_skeptic": "회의론자",
        "seg_pm": "프로덕트 매니저",
        "verdict_positive": "긍정적",
        "verdict_mixed": "복합적",
        "verdict_skeptical": "회의적",
        "verdict_negative": "부정적",
    },
    "Japanese": {
        "overall_verdict": "総合評価",
        "based_on": "{n}件のシミュレーションインタラクションに基づく",
        "segment_reactions": "セグメント別反応",
        "criticism_patterns": "批判パターン",
        "improvement_suggestions": "改善提案",
        "mentions": "{n}回言及",
        "seg_developer": "開発者",
        "seg_investor": "投資家",
        "seg_early_adopter": "アーリーアダプター",
        "seg_skeptic": "懐疑論者",
        "seg_pm": "プロダクトマネージャー",
        "verdict_positive": "肯定的",
        "verdict_mixed": "混合",
        "verdict_skeptical": "懐疑的",
        "verdict_negative": "否定的",
    },
    "Chinese": {
        "overall_verdict": "综合评估",
        "based_on": "基于{n}次模拟互动",
        "segment_reactions": "细分市场反应",
        "criticism_patterns": "批评模式",
        "improvement_suggestions": "改进建议",
        "mentions": "提及{n}次",
        "seg_developer": "开发者",
        "seg_investor": "投资者",
        "seg_early_adopter": "早期采用者",
        "seg_skeptic": "怀疑者",
        "seg_pm": "产品经理",
        "verdict_positive": "积极",
        "verdict_mixed": "复杂",
        "verdict_skeptical": "怀疑",
        "verdict_negative": "消极",
    },
    "Spanish": {
        "overall_verdict": "Veredicto General",
        "based_on": "Basado en {n} interacciones simuladas",
        "segment_reactions": "Reacciones por Segmento",
        "criticism_patterns": "Patrones de Crítica",
        "improvement_suggestions": "Sugerencias de Mejora",
        "mentions": "mencionado {n} veces",
        "seg_developer": "Desarrollador",
        "seg_investor": "Inversor",
        "seg_early_adopter": "Adoptante Temprano",
        "seg_skeptic": "Escéptico",
        "seg_pm": "Product Manager",
        "verdict_positive": "Positivo",
        "verdict_mixed": "Mixto",
        "verdict_skeptical": "Escéptico",
        "verdict_negative": "Negativo",
    },
    "French": {
        "overall_verdict": "Verdict Global",
        "based_on": "Basé sur {n} interactions simulées",
        "segment_reactions": "Réactions par Segment",
        "criticism_patterns": "Patterns de Critique",
        "improvement_suggestions": "Suggestions d'Amélioration",
        "mentions": "mentionné {n} fois",
        "seg_developer": "Développeur",
        "seg_investor": "Investisseur",
        "seg_early_adopter": "Adopteur Précoce",
        "seg_skeptic": "Sceptique",
        "seg_pm": "Product Manager",
        "verdict_positive": "Positif",
        "verdict_mixed": "Mixte",
        "verdict_skeptical": "Sceptique",
        "verdict_negative": "Négatif",
    },
    "German": {
        "overall_verdict": "Gesamtbewertung",
        "based_on": "Basierend auf {n} simulierten Interaktionen",
        "segment_reactions": "Segmentreaktionen",
        "criticism_patterns": "Kritikuster",
        "improvement_suggestions": "Verbesserungsvorschläge",
        "mentions": "{n}x erwähnt",
        "seg_developer": "Entwickler",
        "seg_investor": "Investor",
        "seg_early_adopter": "Early Adopter",
        "seg_skeptic": "Skeptiker",
        "seg_pm": "Produktmanager",
        "verdict_positive": "Positiv",
        "verdict_mixed": "Gemischt",
        "verdict_skeptical": "Skeptisch",
        "verdict_negative": "Negativ",
    },
    "Portuguese": {
        "overall_verdict": "Veredicto Geral",
        "based_on": "Baseado em {n} interações simuladas",
        "segment_reactions": "Reações por Segmento",
        "criticism_patterns": "Padrões de Crítica",
        "improvement_suggestions": "Sugestões de Melhoria",
        "mentions": "mencionado {n} vezes",
        "seg_developer": "Desenvolvedor",
        "seg_investor": "Investidor",
        "seg_early_adopter": "Adotante Inicial",
        "seg_skeptic": "Cético",
        "seg_pm": "Gerente de Produto",
        "verdict_positive": "Positivo",
        "verdict_mixed": "Misto",
        "verdict_skeptical": "Cético",
        "verdict_negative": "Negativo",
    },
    "English": {
        "overall_verdict": "Overall Verdict",
        "based_on": "Based on {n} simulated interactions",
        "segment_reactions": "Segment Reactions",
        "criticism_patterns": "Criticism Patterns",
        "improvement_suggestions": "Improvement Suggestions",
        "mentions": "mentioned {n}x",
        "seg_developer": "Developer",
        "seg_investor": "Investor",
        "seg_early_adopter": "Early Adopter",
        "seg_skeptic": "Skeptic",
        "seg_pm": "Product Manager",
        "verdict_positive": "Positive",
        "verdict_mixed": "Mixed",
        "verdict_skeptical": "Skeptical",
        "verdict_negative": "Negative",
    },
}


def _render_report_md(report: dict, idea_text: str, language: str) -> str:
    t = _REPORT_I18N.get(language, _REPORT_I18N["English"])
    verdict_emoji = _VERDICT_EMOJI.get(report.get("verdict", "mixed"), "⚖️")
    verdict_raw = report.get("verdict", "mixed")
    verdict_label = t.get(f"verdict_{verdict_raw}", verdict_raw.title())

    seg_name_map = {
        "developer": t["seg_developer"],
        "investor": t["seg_investor"],
        "early_adopter": t["seg_early_adopter"],
        "skeptic": t["seg_skeptic"],
        "pm": t["seg_pm"],
    }

    lines = [
        f"## {verdict_emoji} {t['overall_verdict']}: {verdict_label}",
        f"*{t['based_on'].format(n=report.get('evidence_count', 0))}*",
        f"",
        f"## {t['segment_reactions']}",
    ]
    for seg in report.get("segments", []):
        sentiment_icon = _SENTIMENT_ICON.get(seg.get("sentiment", "neutral"), "😐")
        seg_key = seg.get("name", "").lower()
        seg_label = seg_name_map.get(seg_key, seg_key.replace("_", " ").title())
        lines.append(f"### {sentiment_icon} {seg_label}")
        lines.append(seg.get("summary", ""))
        for q in seg.get("key_quotes", []):
            q = q.strip().strip('"\u201c\u201d')
            lines.append(f'> "{q}"')
        lines.append("")

    lines += [f"## {t['criticism_patterns']}"]
    for cluster in report.get("criticism_clusters", []):
        n = cluster.get("count", 0)
        lines.append(f"### {cluster.get('theme', '')} ({t['mentions'].format(n=n)})")
        for ex in cluster.get("examples", [])[:2]:
            ex = ex.strip().strip('"\u201c\u201d')
            lines.append(f'- "{ex}"')
        lines.append("")

    lines += [f"## {t['improvement_suggestions']}"]
    for imp in report.get("improvements", []):
        freq = imp.get("frequency", 1)
        lines.append(f"- **{imp.get('suggestion', '')}** *({t['mentions'].format(n=freq)})*")

    return "\n".join(lines)
