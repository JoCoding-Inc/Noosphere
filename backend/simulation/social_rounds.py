from __future__ import annotations
import asyncio
import dataclasses
import logging
import random
import re
import uuid
from collections.abc import AsyncGenerator
from difflib import SequenceMatcher

from backend.simulation.models import Persona, SocialPost, PlatformState
from backend.simulation.persona_generator import (
    generate_persona, sample_persona_names, _validate_persona_distribution,
    _PLATFORM_ARCHETYPES, _DEFAULT_ARCHETYPES,
)
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
_SENTIMENT_ICON: dict[str, str] = {"positive": "👍", "neutral": "😐", "negative": "👎", "constructive": "🔧"}

# ── Creator impersonation filter patterns ────────────────────────────────────
_CREATOR_PATTERNS = [
    re.compile(r"\bi built\b", re.I),
    re.compile(r"\bwe (built|created|made|developed)\b", re.I),
    re.compile(r"\bour (product|startup|app|tool|service)\b", re.I),
    re.compile(r"\bas (the |a )?founder\b", re.I),
    re.compile(r"\bi'?m the (creator|founder|maker|developer)\b", re.I),
    re.compile(r"\bmy startup\b", re.I),
    re.compile(r"\bwe launched\b", re.I),
]


def _is_creator_impersonation(content: str) -> bool:
    """2개 이상의 창작자 패턴이 매칭되면 True"""
    hits = sum(1 for p in _CREATOR_PATTERNS if p.search(content))
    return hits >= 2


def _to_openai_tool(tool: dict) -> dict:
    return {
        "type": "function",
        "function": {
            "name": tool["name"],
            "description": tool.get("description", ""),
            "parameters": tool["input_schema"],
        }
    }


def _update_emotional_state(persona: Persona) -> None:
    """attitude_shift 기반으로 emotional_state를 동적 업데이트"""
    shift = persona.attitude_shift
    if shift is None:
        return
    if shift >= 0.4:
        persona.emotional_state = "enthusiastically convinced"
    elif shift >= 0.25:
        persona.emotional_state = "warming up"
    elif shift >= 0.1:
        persona.emotional_state = "cautiously optimistic"
    elif shift <= -0.4:
        persona.emotional_state = "strongly opposed"
    elif shift <= -0.25:
        persona.emotional_state = "increasingly skeptical"
    elif shift <= -0.1:
        persona.emotional_state = "mildly concerned"
    # -0.1 < shift < 0.1: initial_emotional_state 복원
    else:
        persona.emotional_state = persona.initial_emotional_state or "neutral"


def _sentiment_polarity(sentiment: str) -> str:
    """sentiment를 polarity 그룹으로 분류. positive/constructive -> 'pos', negative -> 'neg', 그 외 -> 'neutral'"""
    if sentiment in ("positive", "constructive"):
        return "pos"
    if sentiment == "negative":
        return "neg"
    return "neutral"


def _update_interaction_ledger(
    persona: Persona,
    post,
    state,
    personas,
) -> None:
    """Record pairwise interaction in both participants' ledgers.

    Only applies to reply-type posts (parent_id is set). Skips self-replies
    and replies to the seed post.
    """
    if not post.parent_id:
        return
    parent_post = state.get_post(post.parent_id)
    if parent_post is None:
        return
    counterpart_nid = parent_post.author_node_id
    if counterpart_nid == persona.node_id or counterpart_nid == "__seed__":
        return

    _default_entry = lambda: {
        "exchanges": 0, "my_last_sentiment": "", "their_last_sentiment": "",
        "last_round": 0, "agreed_count": 0, "disagreed_count": 0,
    }

    # --- Forward ledger (persona -> counterpart) ---
    ledger = persona.interaction_ledger.setdefault(counterpart_nid, _default_entry())
    ledger["exchanges"] += 1
    ledger["last_round"] = getattr(post, "round_num", 0)
    ledger["my_last_sentiment"] = post.sentiment or ""
    ledger["their_last_sentiment"] = parent_post.sentiment or ""
    reply_pol = _sentiment_polarity(post.sentiment or "")
    parent_pol = _sentiment_polarity(parent_post.sentiment or "")
    if reply_pol != "neutral" and parent_pol != "neutral":
        if reply_pol == parent_pol:
            ledger["agreed_count"] += 1
        else:
            ledger["disagreed_count"] += 1

    # --- Reverse ledger (counterpart -> persona) ---
    if isinstance(personas, dict):
        counterpart = personas.get(counterpart_nid)
    else:
        counterpart = next((p for p in personas if p.node_id == counterpart_nid), None)
    if counterpart:
        c_ledger = counterpart.interaction_ledger.setdefault(persona.node_id, _default_entry())
        c_ledger["exchanges"] += 1
        c_ledger["last_round"] = ledger["last_round"]
        c_ledger["their_last_sentiment"] = post.sentiment or ""
        c_ledger["my_last_sentiment"] = parent_post.sentiment or ""
        if reply_pol != "neutral" and parent_pol != "neutral":
            if reply_pol == parent_pol:
                c_ledger["agreed_count"] += 1
            else:
                c_ledger["disagreed_count"] += 1


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
        for kw in _normalized_list(persona.interests) & _normalized_list(doc.get("_keywords")):
            score += 2 if len(kw) >= 3 else 1
        for kw in _normalized_list(persona.interests) & _normalized_list(doc.get("_entities")):
            score += 2 if len(kw) >= 3 else 1
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
    total_rounds: int = 8,
    mentioned_agents: dict[str, list[str]] | None = None,
    phase_ratio: float = 0.0,
) -> list[Persona]:
    """Phase-adaptive new/returning split + cooldown-idle random selection.

    k_new:k_return ratio adapts by phase:
      Phase 1 (<=0.33): 70:30 — maximise fresh voices
      Phase 2 (<=0.66): 50:50 — returning agents re-engage for debate
      Phase 3 (>0.66):  40:60 — returning agents dominate for synthesis

    recent_speakers: node_id -> last round they produced content.
    posts: all platform posts used to find which returning agents received replies.
    total_rounds: total number of rounds in the simulation (for adaptive cooldown).
    Returns at least 1 agent when personas is non-empty; returns [] if personas is empty.

    Cooldown is adaptive: starts at 3 in the first half, decays linearly to 1 in
    the final rounds so late-round activity doesn't cliff.  If the pool is still
    too small after adaptive cooldown, it falls back to cooldown=1.
    """
    if not personas:
        return []
    k = max(1, round(len(personas) * activation_rate))
    # Phase-adaptive k_new / k_return split
    if phase_ratio <= 0.33:
        new_ratio = 0.7   # Phase 1: 70% new, 30% returning
    elif phase_ratio <= 0.66:
        new_ratio = 0.5   # Phase 2: 50% new, 50% returning
    else:
        new_ratio = 0.4   # Phase 3: 40% new, 60% returning
    k_new = round(k * new_ratio)
    k_return = k - k_new

    speakers = recent_speakers or {}

    # Adaptive cooldown: shrinks in later rounds to prevent activity cliff.
    # Base cooldown is 3 rounds in the first half; decays to 1 in the final rounds.
    half = max(1, total_rounds // 2)
    if current_round <= half:
        cooldown = 3
    else:
        progress = (current_round - half) / max(1, total_rounds - half)
        cooldown = max(1, round(3 - 2 * progress))

    # New pool: agents idle for cooldown+ rounds (never-spoken agents always qualify)
    new_pool = [
        p for p in personas
        if current_round - speakers.get(p.node_id, -99) >= cooldown
    ]

    # Guarantee: if new_pool is too small to fill k_new, relax cooldown to 1
    if len(new_pool) < k_new:
        new_pool = [
            p for p in personas
            if current_round - speakers.get(p.node_id, -99) >= 1
        ]
    # Weighted selection: enthusiastic personas participate more
    # innovation_openness + commercial_focus*0.5 + (10-skepticism)*0.5
    weights = []
    for p in new_pool:
        w = (
            getattr(p, 'innovation_openness', 5)
            + getattr(p, 'commercial_focus', 5) * 0.5
            + (10 - getattr(p, 'skepticism', 5)) * 0.5
        ) / 25.0
        # Extraverted MBTI types get a small activation bonus
        if getattr(p, 'mbti', '') and p.mbti and p.mbti[0] == 'E':
            w += 0.05
        weights.append(max(0.1, w))  # minimum 0.1 to ensure all agents have a chance

    # Spiral of Silence: Phase 3에서 지배적 감정과 반대 입장 에이전트의 활동 억제
    if phase_ratio > 0.66 and posts:
        _max_rn = max((pp.round_num for pp in posts), default=0)
        recent_posts = [p for p in posts if p.round_num == _max_rn - 1]
        if recent_posts:
            from collections import Counter
            sent_counts = Counter(p.sentiment or 'neutral' for p in recent_posts if p.sentiment)
            total_sent = sum(sent_counts.values()) or 1
            dominant_sent, dominant_count = sent_counts.most_common(1)[0] if sent_counts else ('neutral', 0)
            dominant_ratio = dominant_count / total_sent

            if dominant_ratio >= 0.6:
                _positive_sentiments = {'positive', 'constructive'}
                dom_is_positive = dominant_sent in _positive_sentiments

                for i, persona in enumerate(new_pool):
                    if getattr(persona, 'skepticism', 5) >= 8:
                        continue  # 극단적 회의론자는 면역
                    attitude = getattr(persona, 'attitude_shift', 0.0) or 0.0
                    persona_is_positive = attitude >= 0
                    # 지배적 감정과 반대 방향이면 패널티
                    if dom_is_positive != persona_is_positive:
                        spiral_penalty = max(0.3, 1.0 - (dominant_ratio - 0.5) * 1.5)
                        weights[i] = weights[i] * spiral_penalty

    selected_new = []
    pool_copy = list(new_pool)
    weights_copy = list(weights)
    for _ in range(min(k_new, len(pool_copy))):
        if not pool_copy:
            break
        chosen = random.choices(pool_copy, weights=weights_copy, k=1)[0]
        idx = pool_copy.index(chosen)
        selected_new.append(chosen)
        pool_copy.pop(idx)
        weights_copy.pop(idx)
    selected_ids = {p.node_id for p in selected_new}

    # NOTE: no surplus transfer — new-agent shortfall does NOT bleed into returning pool.
    # This prevents the same agents from bypassing the cooldown.

    # Returning pool: previously spoken, not already selected
    returning_pool = [
        p for p in personas
        if p.node_id not in selected_ids and p.node_id in speakers
    ]

    # Prioritize returning agents whose posts received replies, then attitude-shifted agents
    if posts:
        post_author: dict[str, str] = {post.id: post.author_node_id for post in posts}
        replied_authors: set[str] = {
            post_author[post.parent_id]
            for post in posts
            if post.parent_id and post.parent_id in post_author
        }
        prioritized = [p for p in returning_pool if p.node_id in replied_authors]
        random.shuffle(prioritized)

        # Attitude-shifted agents (|shift| > 0.1) get secondary priority
        replied_node_ids = {p.node_id for p in prioritized}
        attitude_shifted = [
            p for p in returning_pool
            if p.node_id not in replied_node_ids
            and abs(getattr(p, 'attitude_shift', 0) or 0) > 0.1
        ]
        attitude_shifted.sort(key=lambda p: -abs(getattr(p, 'attitude_shift', 0) or 0))

        fallback_ids = replied_node_ids | {p.node_id for p in attitude_shifted}
        remaining = [p for p in returning_pool if p.node_id not in fallback_ids]
        random.shuffle(remaining)

        ordered_returning = prioritized + attitude_shifted + remaining
    else:
        random.shuffle(returning_pool)
        ordered_returning = returning_pool

    selected_return = ordered_returning[:k_return]
    selected = selected_new + selected_return

    # Fill remaining slots from leftover new pool + returning pool remainders (cooldown >= 1)
    if len(selected) < k:
        leftover_ids = {p.node_id for p in selected}
        extra_new = [p for p in new_pool if p.node_id not in leftover_ids]
        extra_returning = [
            p for p in returning_pool
            if p.node_id not in leftover_ids
            and current_round - speakers.get(p.node_id, -99) >= 1
        ]
        extra = extra_new + extra_returning
        selected += extra[:k - len(selected)]

    # ── Skepticism diversity correction: ensure at least 20% are skeptical (skepticism >= 7) ──
    if selected:
        min_skeptics = max(1, round(len(selected) * 0.2))
        current_skeptics = [p for p in selected if getattr(p, "skepticism", 5) >= 7]
        if len(current_skeptics) < min_skeptics:
            selected_ids_final = {p.node_id for p in selected}
            # Find unselected skeptical agents, sorted by skepticism descending
            skeptic_candidates = sorted(
                [p for p in personas if p.node_id not in selected_ids_final and getattr(p, "skepticism", 5) >= 7],
                key=lambda p: -getattr(p, "skepticism", 5),
            )
            needed = min_skeptics - len(current_skeptics)
            # Replace the least-skeptical non-skeptic agents with skeptical ones
            if skeptic_candidates:
                non_skeptics = sorted(
                    [p for p in selected if getattr(p, "skepticism", 5) < 7],
                    key=lambda p: getattr(p, "skepticism", 5),
                )
                replacements = min(needed, len(skeptic_candidates), len(non_skeptics))
                for i in range(replacements):
                    # Remove the least skeptical agent and add a skeptical one
                    selected.remove(non_skeptics[i])
                    selected.append(skeptic_candidates[i])

    # ── Mention priority: agents mentioned via @Name bypass cooldown ──
    if mentioned_agents:
        personas_by_id = {p.node_id: p for p in personas}
        selected_ids_mention = {p.node_id for p in selected}
        for node_id in list(mentioned_agents.keys()):
            if node_id not in selected_ids_mention and node_id in personas_by_id:
                selected.append(personas_by_id[node_id])
                selected_ids_mention.add(node_id)

    # ── Generation diversity correction: ensure Gen X/Boomer representation ──
    if len(selected) >= 5:
        gen_xb = [p for p in selected if p.generation in ("Gen X", "Boomer")]
        gen_xb_ratio = len(gen_xb) / len(selected)
        if gen_xb_ratio < 0.15:
            selected_ids_gen = {p.node_id for p in selected}
            gen_xb_candidates = [
                p for p in personas
                if p.node_id not in selected_ids_gen and p.generation in ("Gen X", "Boomer")
            ]
            if gen_xb_candidates:
                # Replace one Gen Z agent with a Gen X/Boomer agent (max 1 swap)
                gen_z_in_selected = [p for p in selected if p.generation == "Gen Z"]
                if gen_z_in_selected:
                    selected.remove(gen_z_in_selected[0])
                    selected.append(gen_xb_candidates[0])

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
        f"You are creating the FIRST post on {platform.name}. "
        f"Fill in ALL structured fields to make this feel native to {platform.name}. "
        f"Match the platform's tone and style exactly. Write in {language}.\n",
        "If the idea description contains specific numbers (market size, pricing, metrics, revenue projections, user counts), "
        "you MUST include those exact figures in the seed post. Concrete data points make the community discussion more grounded and valuable.\n",
    ]
    if platform.seed_controversy_hint:
        context_lines.append(f"Controversy hint: {platform.seed_controversy_hint}\n")
    context_lines.append(f"Idea: {idea_text}")
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
        sentiment="neutral",
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


def _build_thread_context(state: PlatformState, target_post_id: str | None, max_depth: int = 3, max_siblings: int = 2, children_map: dict | None = None) -> str:
    """Reply 타겟의 스레드 전체 맥락(조상 포스트 + 형제 댓글)을 구축하여 반환.

    - parent_id 체인을 따라 올라가며 조상 포스트 수집 (max_depth까지)
    - 타겟의 형제 포스트(같은 parent_id, 다른 author) 중 upvotes 상위 max_siblings개 수집
    - 전체 출력 600자 이내로 자름
    - target_post_id가 None이거나 root post(parent_id 없음)면 빈 문자열 반환
    """
    if not target_post_id or not state:
        return ""
    target = state.get_post(target_post_id)
    if not target:
        return ""
    # root post (no parent) -> no thread context needed
    if not target.parent_id:
        return ""

    # Collect ancestors by walking up parent_id chain
    ancestors: list[SocialPost] = []
    current_id = target.parent_id
    for _ in range(max_depth):
        if not current_id:
            break
        ancestor = state.get_post(current_id)
        if not ancestor:
            break
        ancestors.append(ancestor)
        current_id = ancestor.parent_id

    # Reverse so root is first
    ancestors.reverse()

    # Collect siblings: same parent_id, different author
    siblings: list[SocialPost] = []
    if target.parent_id:
        if children_map is not None:
            sibling_candidates = [
                p for p in children_map.get(target.parent_id, [])
                if p.id != target.id
                and p.author_node_id != target.author_node_id
            ]
        else:
            sibling_candidates = [
                p for p in state.posts
                if p.parent_id == target.parent_id
                and p.id != target.id
                and p.author_node_id != target.author_node_id
            ]
        sibling_candidates.sort(key=lambda p: p.upvotes, reverse=True)
        siblings = sibling_candidates[:max_siblings]

    # Build output
    lines: list[str] = ["[THREAD CONTEXT]"]
    for i, anc in enumerate(ancestors):
        prefix = "  " * i
        label = "Root" if i == 0 else f"L{i}"
        lines.append(f"{prefix}{label}: @{anc.author_name}: {anc.content[:150]}")

    # Target line
    target_indent = "  " * len(ancestors)
    lines.append(f"{target_indent}Target: @{target.author_name}: {target.content[:200]}")

    # Siblings
    for sib in siblings:
        sib_indent = "  " * max(len(ancestors) - 1, 0)
        lines.append(f"{sib_indent}[Sibling] @{sib.author_name}: {sib.content[:100]} ({sib.upvotes} upvotes)")

    result = "\n".join(lines)
    # Truncate to 600 chars
    if len(result) > 600:
        result = result[:597] + "..."
    return result


def _compute_argument_quality(reply: "SocialPost") -> float:
    """Argument quality multiplier (0.3 ~ 2.0) based on content signals."""
    content = reply.content or ""
    words = content.split()
    word_count = len(words)

    # Signal 1: content depth (word count / 40, cap 1.0)
    content_depth = min(word_count / 40.0, 1.0)

    # Signal 2: evidence signal (numbers, comparisons, citations)
    ev_patterns = [
        r'\d+%',            # percentages
        r'\d+x\b',          # multipliers
        r'\b\d{4}\b',       # years/numbers
        r'https?://',       # links
        r'\bvs\.?\b',       # comparisons
        r'\bcompared\b',
        r'\baccording\b',
        r'\bstudy\b',
        r'\bdata\b',
        r'\bsource\b',
    ]
    ev_hits = sum(1 for p in ev_patterns if re.search(p, content, re.IGNORECASE))
    evidence_signal = min(ev_hits * 0.15, 0.6)

    # Signal 3: community validation
    upvotes = max(reply.upvotes or 0, 0)
    community_validation = min(upvotes / 10.0, 1.0)

    quality = content_depth + evidence_signal + community_validation
    # Normalize to 0.3 ~ 2.0
    return max(0.3, min(2.0, quality))


def _build_cascade_signal(state: "PlatformState", round_num: int) -> str:
    """Phase 1-2 early-round 정보 캐스케이드 신호. 현재 라운드 첫 3개 포스트 sentiment 확인."""
    current_posts = [p for p in state.posts if p.round_num == round_num]
    if len(current_posts) < 3:
        return ""
    early_three = sorted(current_posts, key=lambda p: p.id)[:3]
    from collections import Counter as _C
    sents = [p.sentiment for p in early_three if p.sentiment]
    if not sents:
        return ""
    most_common, count = _C(sents).most_common(1)[0]
    if count >= 2:
        return (
            f"[CASCADE SIGNAL] Early responders are strongly {most_common} "
            f"({count}/3 posts). Community attention is gravitating toward this viewpoint."
        )
    return ""


def _build_compact_feed(posts: list, top_n: int = 8, persona=None, round_num: int = 0, personas_map: dict | None = None, my_post_ids: set | None = None, children_map: dict | None = None) -> str:
    """decide_action용 compact feed: ID/author/sentiment/50자 요약만 포함.

    full content 대신 핵심 메타만 전달하여 토큰 절감.

    diversity-aware 샘플링:
    - 상위 4개: weighted_score 내림차순 (인기 포스트)
    - underexplored 2개: reply_count 0-1, 최근 2라운드 내, seed/post/comment만
    - opposing 2개: persona attitude_shift 반대 감정 포스트
    - 합집합이 top_n 미만이면 weighted_score로 나머지 채움
    """
    posts = [p for p in posts if getattr(p, 'author_node_id', '') != "__seed__"]
    if not posts:
        return ""

    def _format_line(p, prefix: str = "") -> str:
        content = getattr(p, "content", "") or ""
        snippet = (content[:50] + "...") if len(content) > 50 else content
        sent = getattr(p, "sentiment", "") or "neutral"
        up = getattr(p, "upvotes", 0)
        rc = getattr(p, "reply_count", 0)
        tag = f"{prefix} " if prefix else ""
        return f"{tag}[{p.id}] @{p.author_name} ({sent}, +{up}, {rc} replies): {snippet}"

    # persona가 없으면 기존 방식 fallback
    if persona is None:
        sorted_posts = sorted(posts, key=lambda p: getattr(p, "weighted_score", 0) or 0, reverse=True)[:top_n]
        return "\n".join(_format_line(p) for p in sorted_posts)

    # --- diversity-aware 샘플링 ---

    # 1) 상위 4개: weighted_score 내림차순
    by_score = sorted(posts, key=lambda p: getattr(p, "weighted_score", 0) or 0, reverse=True)
    top_posts = by_score[:4]
    selected_ids = {p.id for p in top_posts}

    # 2) underexplored 2개: reply_count 0-1, 최근 2라운드 내, seed/post/comment action_type
    underexplored_posts: list = []
    if round_num > 0:
        content_actions = {"seed", "post", "comment", "new_post", "review", "question", "milestone_update", "reply"}
        candidates = [
            p for p in posts
            if p.id not in selected_ids
            and getattr(p, "reply_count", 0) <= 1
            and getattr(p, "round_num", 0) >= round_num - 2
            and getattr(p, "action_type", "") in content_actions
        ]
        candidates.sort(key=lambda p: getattr(p, "weighted_score", 0) or 0, reverse=True)
        underexplored_posts = candidates[:2]
        selected_ids.update(p.id for p in underexplored_posts)

    # 3) opposing 2개: attitude_shift 반대 감정 포스트
    opposing_posts: list = []
    attitude = getattr(persona, "attitude_shift", 0.0)
    if attitude >= 0:
        target_sentiment = "negative"
    else:
        target_sentiment = "positive"
    opp_candidates = [
        p for p in by_score
        if p.id not in selected_ids
        and getattr(p, "sentiment", "") == target_sentiment
    ]
    opposing_posts = opp_candidates[:2]
    selected_ids.update(p.id for p in opposing_posts)

    # 4) opinion leader posts (lead/principal/director/vp/c_suite)
    _LEADER_SENIORITY = {'lead', 'principal', 'director', 'vp', 'c_suite'}
    opinion_leaders_2: list = []
    if personas_map:
        ol_candidates = []
        for p in posts:
            if p.id in selected_ids:
                continue
            author = personas_map.get(p.author_node_id)
            seniority = (getattr(author, 'seniority', '') or '').lower()
            if seniority in _LEADER_SENIORITY:
                ol_candidates.append(p)
        ol_candidates.sort(key=lambda p: (p.weighted_score or 0), reverse=True)
        opinion_leaders_2 = ol_candidates[:2]
        selected_ids.update(p.id for p in opinion_leaders_2)

    # 5) [REPLY TO YOU]: 자기 포스트에 달린 최신 reply 최대 2개 (논쟁 참여 유도)
    reply_to_you_posts: list = []
    if my_post_ids:
        if children_map is not None:
            # children_map 활용: my_post_ids의 children 수집
            _reply_candidates = []
            for _my_id in my_post_ids:
                _reply_candidates.extend(children_map.get(_my_id, []))
            # 자기 자신 제외 + 이미 선택된 포스트 제외
            _reply_candidates = [
                p for p in _reply_candidates
                if p.id not in selected_ids
                and getattr(p, 'author_node_id', '') != (getattr(persona, 'node_id', '') if persona else '')
            ]
        else:
            # fallback: posts 리스트에서 parent_id가 my_post_ids에 속하는 것
            _reply_candidates = [
                p for p in posts
                if getattr(p, 'parent_id', None) in my_post_ids
                and p.id not in selected_ids
                and getattr(p, 'author_node_id', '') != (getattr(persona, 'node_id', '') if persona else '')
            ]
        _reply_candidates.sort(key=lambda p: getattr(p, 'round_num', 0), reverse=True)
        reply_to_you_posts = _reply_candidates[:2]
        selected_ids.update(p.id for p in reply_to_you_posts)

    # 6) 합집합이 top_n 미만이면 나머지를 weighted_score로 채움
    all_selected = list(reply_to_you_posts) + list(top_posts) + list(underexplored_posts) + list(opposing_posts) + list(opinion_leaders_2)
    if len(all_selected) < top_n:
        filler = [p for p in by_score if p.id not in selected_ids]
        all_selected.extend(filler[: top_n - len(all_selected)])

    # 태그를 붙여서 포맷팅
    reply_to_you_ids = {p.id for p in reply_to_you_posts}
    underexplored_ids = {p.id for p in underexplored_posts}
    opposing_ids = {p.id for p in opposing_posts}
    opinion_leader_ids = {p.id for p in opinion_leaders_2}
    lines = []
    for p in all_selected:
        if p.id in reply_to_you_ids:
            lines.append(_format_line(p, prefix="[REPLY TO YOU]"))
        elif p.id in opinion_leader_ids:
            lines.append(_format_line(p, prefix="[OPINION LEADER]"))
        elif p.id in underexplored_ids:
            lines.append(_format_line(p, prefix="[UNDEREXPLORED]"))
        elif p.id in opposing_ids:
            lines.append(_format_line(p, prefix="[OPPOSING VIEW]"))
        else:
            lines.append(_format_line(p))
    result = "\n".join(lines)
    # Append targetable IDs line: full UUIDs for LLM to copy into target_post_id
    targetable_ids = [p.id for p in all_selected]
    if targetable_ids:
        result += f"\n[Targetable IDs: {', '.join(targetable_ids)}]"
    return result


async def decide_action(
    persona: Persona,
    platform: AbstractPlatform,
    feed_text: str,
    language: str = "English",
    round_num: int = 1,
    total_rounds: int = 8,
    persona_history: list | None = None,
) -> AgentAction:
    """LLM call 1: decide action_type and target_post_id."""
    allowed = platform.get_allowed_actions(persona)
    # Add "pass" option only in later rounds (>= 60% of total_rounds)
    if round_num >= total_rounds * 0.6 and "pass" not in allowed:
        allowed = list(allowed) + ["pass"]
    content_actions = [a for a in allowed if a not in platform.no_content_actions]
    content_bias = (
        f"IMPORTANT: You MUST choose a content-writing action ({', '.join(content_actions)}) "
        f"unless there is truly nothing worth saying. Passive actions like upvote/flag should be rare exceptions. "
        f"Aim to write substantive content at least 80% of the time.\n"
    ) if content_actions else ""
    # Per-action descriptions for diversity
    _action_desc: dict[str, str] = {
        "comment": "Add your perspective or opinion on the topic",
        "reply": "Respond directly to another person's comment",
        "post": "Create a new top-level discussion thread",
        "new_post": "Submit a new top-level post or link",
        "share": "Reshare content with your own framing",
        "share_experience": "Tell a personal story or lesson from your experience",
        "ask_advice": "Ask the community a focused, actionable question",
        "question": "Ask a question about the product or idea",
        "review": "Write a structured review of the product",
        "upvote": "Upvote a post you find valuable",
        "downvote": "Downvote a post you find unhelpful",
        "react": "React to a post (Like, Insightful, etc.)",
        "flag": "Flag inappropriate or low-quality content",
        "milestone": "Share a milestone achievement (first customer, revenue, launch, pivot)",
        "article": "Write a long-form article with a key takeaway",
        "pass": "Read only — you observe but don't post this round (use sparingly)",
    }
    # Emotional-state-based action ordering: move relevant actions to the front
    _negative_emotions = {"strongly opposed", "frustrated", "skeptical"}
    _positive_emotions = {"enthusiastically", "positive", "impressed"}
    _emo = (persona.emotional_state or "").lower()
    if any(kw in _emo for kw in _negative_emotions):
        _critical = {"downvote", "flag"}
        allowed = [a for a in allowed if a in _critical] + [a for a in allowed if a not in _critical]
    elif any(kw in _emo for kw in _positive_emotions):
        _approval = {"upvote", "react"}
        allowed = [a for a in allowed if a in _approval] + [a for a in allowed if a not in _approval]

    action_list_lines = "\n".join(
        f"  - {a}: {_action_desc.get(a, 'Perform this action')}"
        for a in allowed
    )
    # Phase-based hint for action selection
    _phase_ratio = round_num / max(total_rounds, 1)
    if _phase_ratio <= 0.33:
        phase_action_hint = ""
    elif _phase_ratio <= 0.66:
        phase_action_hint = "This is the debate phase — prefer reply or comment actions that challenge others' arguments.\n"
    else:
        phase_action_hint = "This is the synthesis phase — asking questions or sharing experiences is especially valuable.\n"
    # JTBD hint: align action choice with persona's job-to-be-done
    jtbd_hint = ""
    if persona.jtbd:
        jtbd_hint = (
            f"\nYour primary job-to-be-done: {persona.jtbd}\n"
            f"Choose an action that aligns with what you are trying to accomplish.\n"
        )
        if any(k in persona.jtbd.lower() for k in ["evaluat", "compar", "learn", "research", "understand", "assess"]):
            jtbd_hint += "Given your JTBD involves evaluation or research, asking pointed questions is encouraged.\n"

    # Cognitive pattern hint: shape action choice by thinking style
    cognitive_hint = ""
    if persona.cognitive_pattern:
        cognitive_hint = (
            f"\nYour dominant thinking pattern: '{persona.cognitive_pattern}'. "
            f"Let this shape which type of action you choose.\n"
        )

    # MBTI hint: personality-driven action tendency
    mbti_hint = ""
    if persona.mbti:
        is_extrovert = persona.mbti[0] == 'E'
        is_thinking = persona.mbti[2] == 'T' if len(persona.mbti) >= 3 else True
        mbti_hint = (
            f"\nPersonality type: {persona.mbti}. "
            f"As an {'Extraverted' if is_extrovert else 'Introverted'} type, you tend to {'engage readily and share openly' if is_extrovert else 'observe more and choose words carefully'}. "
            f"As a {'Thinking' if is_thinking else 'Feeling'} type, you lead with {'logic and data-driven arguments' if is_thinking else 'values and human impact'}.\n"
        )

    # Build action history summary for diversity (token-efficient: no content, just action/upvote)
    action_history_hint = ""
    diversity_hint = ""
    if persona_history:
        sorted_hist = sorted(persona_history, key=lambda p: p.round_num)
        hist_lines = []
        for p in sorted_hist[-6:]:  # last 6 actions max
            upvote_str = f"(+{p.upvotes} upvotes)" if p.upvotes else ""
            _sent = getattr(p, 'sentiment', '') or 'neutral'
            hist_lines.append(f"R{p.round_num} {p.action_type}[{_sent}]{upvote_str}")
        action_history_hint = "Your recent actions: " + ", ".join(hist_lines) + "\n"
        # action_type 빈도 집계
        from collections import Counter
        action_counts = Counter(p.action_type for p in persona_history)
        most_used = action_counts.most_common(1)[0]
        if most_used[1] >= 3:  # 3번 이상 같은 action이면
            diversity_hint = f" You've used '{most_used[0]}' {most_used[1]} times already — choose a DIFFERENT action this round."
        else:
            action_dist = ", ".join(f"{k}({v})" for k, v in action_counts.most_common())
            diversity_hint = f" Distribution so far: {action_dist}."

    # Sentiment diversity hint: nudge away from monotone sentiment
    _sentiment_diversity_hint = ""
    if persona_history:
        _sent_counts = Counter(
            (getattr(p, 'sentiment', '') or 'neutral') for p in persona_history
        )
        _sent_summary = ", ".join(f"{s}:{c}" for s, c in _sent_counts.most_common())
        if _sent_counts:
            _top_sent, _top_cnt = _sent_counts.most_common(1)[0]
            if _top_cnt >= 3:
                _sentiment_diversity_hint = (
                    f" Your recent outputs lean heavily {_top_sent}"
                    f" -- consider a contrasting perspective this round."
                )
            elif _sent_summary:
                _sentiment_diversity_hint = f" Sentiment balance so far: {_sent_summary}."

    # Attitude-action alignment hint
    attitude = getattr(persona, "attitude_shift", 0.0) or 0.0
    if attitude >= 0.2:
        attitude_action_hint = "Given your increasingly positive attitude, prefer constructive actions (comment, share_experience) over critical ones (downvote, flag).\n"
    elif attitude <= -0.2:
        attitude_action_hint = "Given your increasing skepticism, prefer critical engagement (reply with counterargument, pointed questions) over passive approval (upvote, react).\n"
    else:
        attitude_action_hint = ""

    # Social proof hint: highlight the most-upvoted post, shaped by persona traits
    social_proof_hint = ""
    _feed_entries = re.findall(r"\[([^\]]+)\]\s+@\S+\s+\([^,]+,\s*\+(\d+),", feed_text)
    if _feed_entries:
        _top_id, _top_up_str = max(_feed_entries, key=lambda x: int(x[1]))
        _top_upvotes = int(_top_up_str)
        if _top_upvotes > 0:
            _skep = getattr(persona, "skepticism", 5) or 5
            _inno = getattr(persona, "innovation_openness", 5) or 5
            # skepticism takes priority as a stronger signal
            if _skep >= 7:
                social_proof_hint = (
                    f"[Social Signal] Post {_top_id[:8]} is heavily upvoted ({_top_upvotes}), "
                    f"but popularity ≠ correctness. You tend to question consensus.\n"
                )
            elif _inno >= 7:
                social_proof_hint = (
                    f"[Social Signal] Post {_top_id[:8]} has the most upvotes ({_top_upvotes}) "
                    f"— it reflects community interest. Consider engaging with it.\n"
                )

    prompt = (
        f"Platform: {platform.name}\n"
        f"Your persona: {persona.name}, {persona.role} at {persona.company} "
        f"({persona.seniority}, {persona.affiliation}, age {persona.age})\n"
        f"Bias: {persona.bias_description()}\n"
        + (f"Emotional state: {persona.emotional_state}\n" if persona.emotional_state else "")
        + action_history_hint
        + jtbd_hint
        + cognitive_hint
        + mbti_hint
        + f"Note: You are a community member reacting to someone else's product idea. You are NOT the creator.\n"
        f"Allowed actions:\n{action_list_lines}\n\n"
        f"{content_bias}"
        f"Vary your action type.{diversity_hint}{_sentiment_diversity_hint}\n"
        f"{phase_action_hint}"
        f"{attitude_action_hint}"
        f"{social_proof_hint}"
        f"{feed_text}\n\n"
        f"Choose one action from {allowed}. "
        f"For vote/react actions, pick a target_post_id from the feed. "
        f"Use the exact post ID from the [Targetable IDs] line when specifying target_post_id. "
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
        action_type = data.get("action_type", allowed[0] if allowed else "pass")
        if action_type not in allowed:
            # Prefer content-producing action over no-content (downvote/flag) for fallback
            _fallback_content = [a for a in allowed if a not in platform.no_content_actions]
            action_type = _fallback_content[0] if _fallback_content else (allowed[0] if allowed else "pass")
        target = data.get("target_post_id") or None
        return AgentAction(action_type=action_type, target_post_id=target)
    except LLMToolRequired:
        raise
    except Exception as exc:
        logger.warning("decide_action failed for %s on %s: %s", persona.node_id, platform.name, exc)
        # Prefer content-producing action over no-content (downvote/flag) for fallback
        _fallback_content = [a for a in allowed if a not in platform.no_content_actions]
        _fallback = _fallback_content[0] if _fallback_content else (allowed[0] if allowed else "pass")
        return AgentAction(action_type=_fallback, target_post_id=f"__seed__{platform.name}")


_NEGATIVE_KEYWORDS = {"terrible", "awful", "waste", "useless", "scam", "fraud", "horrible", "worst", "garbage", "nonsense"}
_POSITIVE_KEYWORDS = {"love", "amazing", "great", "revolutionary", "excellent", "brilliant", "outstanding", "fantastic", "perfect", "innovative"}


def _validate_sentiment(content: str, declared: str) -> str:
    """키워드 기반으로 LLM 선언 sentiment의 명백한 오류를 교정."""
    lower = content.lower()
    neg_count = sum(1 for w in _NEGATIVE_KEYWORDS if w in lower)
    pos_count = sum(1 for w in _POSITIVE_KEYWORDS if w in lower)
    if declared == "positive" and neg_count >= 2 and pos_count == 0:
        return "negative"
    elif declared == "constructive" and neg_count >= 2 and pos_count == 0:
        return "negative"
    if declared == "negative" and pos_count >= 2 and neg_count == 0:
        return "positive"
    _ACCEPTED = {"positive", "neutral", "negative", "constructive"}
    if declared not in _ACCEPTED:
        return "neutral"
    return declared


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
    replies_to_me: list | None = None,
    state: PlatformState | None = None,
    cross_platform_context: str = "",
    round_num: int = 1,
    total_rounds: int = 8,
    interaction_memory: str = "",
    children_map: dict | None = None,
    precomputed_prior: str = "",
) -> tuple[str, dict]:
    """LLM call 2: generate post/comment text. Returns (content_str, structured_data)."""
    tool = _to_openai_tool(platform.content_tool(action.action_type))
    tool_name = tool["function"]["name"]
    if precomputed_prior:
        prior_knowledge = precomputed_prior
    elif cluster_docs_map is not None:
        # Phase-based top_k: reduce prior knowledge docs as rounds progress
        # to save tokens (agents have already absorbed background info)
        phase_ratio = round_num / max(total_rounds, 1)
        prior_top_k = 5 if phase_ratio <= 0.33 else (3 if phase_ratio <= 0.66 else 2)
        prior_knowledge = _build_prior_knowledge(persona.node_id, cluster_docs_map, persona, top_k=prior_top_k)
    else:
        prior_knowledge = ""
    history_section = ""
    if persona_history:
        # Sort by round_num descending (most recent first), limit to 5
        sorted_history = sorted(persona_history, key=lambda p: -p.round_num)[:5]
        lines = []
        for p in sorted_history:
            _sent_label = getattr(p, "sentiment", "") or "neutral"
            _snippet = p.content[:50].replace(chr(10), " ")
            _ellipsis = "..." if len(p.content) > 50 else ""
            lines.append(f'- R{p.round_num} {p.action_type} [{_sent_label}]: "{_snippet}{_ellipsis}"')
        attitude_shift = getattr(persona, "attitude_shift", 0.0)
        # Unified attitude context (replaces separate shift_note + consistency_instruction)
        attitude_context = ""
        abs_shift = abs(attitude_shift)
        if abs_shift >= 0.2:
            direction = "positive" if attitude_shift > 0 else "negative"
            attitude_context = (
                f"\nYour view has shifted significantly ({attitude_shift:+.2f} toward {direction}). "
                f"Explicitly acknowledge this change and explain what arguments moved you."
            )
        elif abs_shift >= 0.1:
            attitude_context = f"\nStay consistent with your stated position (attitude drift: {attitude_shift:+.2f})."
        # abs_shift < 0.1: no attitude instruction needed
        history_section = (
            "Your previous comments in this discussion, most recent first (do NOT repeat the same points — "
            "build on, evolve, or take a new angle instead):\n"
            + "\n".join(lines)
            + attitude_context
            + "\n\n"
        )
    interaction_memory_section = ""
    if interaction_memory:
        interaction_memory_section = f"\n{interaction_memory}\n"
    # cross-platform influence hint
    cross_sync_rounds = []
    if hasattr(persona, "attitude_history") and persona.attitude_history:
        cross_sync_rounds = [
            h["round"] for h in persona.attitude_history
            if h.get("trigger_post_id") == "__cross_sync__"
        ]

    if cross_sync_rounds:
        cross_influence_hint = (
            f"\nYour perspective has been shaped by broader community discussions "
            f"across platforms (rounds {', '.join(map(str, cross_sync_rounds[-3:]))}). "
            f"Reference how this wider sentiment influenced your current thinking.\n"
        )
    else:
        cross_influence_hint = ""
    # Inject thread context for replies (ancestors + siblings) or fallback to 1-line target
    target_post_section = ""
    if action.target_post_id and state:
        thread_context = _build_thread_context(state, action.target_post_id, children_map=children_map)
        if thread_context:
            target_post_section = thread_context + "\n\n"
        else:
            # Fallback: root post or missing ancestors -> simple 1-line summary
            target_post = state.get_post(action.target_post_id)
            if target_post:
                target_post_section = f"You are replying to: {target_post.author_name}: {target_post.content[:300]}\n\n"
    replies_section = ""
    if replies_to_me:
        replies_section = "\nReplies to your previous comments (consider responding):\n"
        for r in replies_to_me[-3:]:  # most recent 3 only
            replies_section += f"- @{r.author_name}: {r.content[:200]}\n"
        replies_section += "\n"
    # Phase calculation for debate escalation (3-phase model)
    phase_ratio = round_num / max(total_rounds, 1)
    if phase_ratio <= 0.33:
        phase_hint = ""  # Phase 1: initial opinions -- no extra instruction
        _conflicting_limit = 2
    elif phase_ratio <= 0.66:
        # Phase 2: debate escalation
        phase_hint = (
            "\nCRITICAL: This is the debate escalation phase. "
            "You MUST directly challenge a specific argument you disagree with. "
            "Reference the specific person by @name if you can. "
            "Reference specific thread context points when challenging arguments. "
            "Be direct and pointed, not vague."
        )
        _conflicting_limit = 4
    else:
        # Phase 3: synthesis / conclusion — no conflicting posts needed
        phase_hint = (
            "\nCRITICAL: This is the synthesis phase. "
            "Summarize where you think the community consensus stands. "
            "If your view has shifted, acknowledge it explicitly. "
            "What key questions remain unresolved? "
            "If there were unresolved debates, briefly note where you stand."
        )
        _conflicting_limit = 0

    # Bandwagon Effect hint (Phase 3 only)
    bandwagon_hint = ""
    if phase_ratio > 0.66 and state and state.posts:
        current_round_posts = [p for p in state.posts if p.round_num == round_num]
        if current_round_posts:
            from collections import Counter as _Counter
            sent_counts = _Counter(p.sentiment or 'neutral' for p in current_round_posts if p.sentiment)
            total_s = sum(sent_counts.values()) or 1
            if sent_counts:
                dom_sent, dom_count = sent_counts.most_common(1)[0]
                dom_ratio = dom_count / total_s
                if dom_ratio >= 0.55:
                    persona_skepticism = getattr(persona, 'skepticism', 5) or 5
                    attitude = getattr(persona, 'attitude_shift', 0.0) or 0.0
                    _pos_sents = {'positive', 'constructive'}
                    persona_is_positive = attitude >= 0
                    dom_is_positive = dom_sent in _pos_sents

                    if persona_skepticism <= 6 and persona_is_positive == dom_is_positive:
                        bandwagon_hint = (
                            f"[Social Momentum] {dom_ratio:.0%} of this round's posts are {dom_sent}. "
                            f"As someone aligned with this sentiment, consider amplifying the consensus "
                            f"with your own specific experience or data point."
                        )
                    elif persona_skepticism >= 7:
                        bandwagon_hint = (
                            f"[Contrarian Signal] {dom_ratio:.0%} of posts are {dom_sent} — groupthink is forming. "
                            f"Point out what the majority might be overlooking."
                        )

    # Build conflicting opinions section to encourage debate
    conflicting_section = ""
    if state and state.posts:
        persona_emotion = getattr(persona, "emotional_state", "") or ""
        persona_skepticism = getattr(persona, "skepticism", 5)
        # Determine persona's likely sentiment orientation
        persona_positive = persona_skepticism < 5 or "optimis" in persona_emotion.lower() or "excit" in persona_emotion.lower()
        opposite_sentiment = "negative" if persona_positive else "positive"
        conflicting_candidates = [
            p for p in state.posts
            if getattr(p, "sentiment", "") == opposite_sentiment
            and p.author_node_id != persona.node_id
            and p.content.strip()
        ]
        # Topic relevance filter: prioritize posts matching persona interests/tech_area
        _stopwords = {"the", "a", "an", "and", "or", "of", "in", "for"}
        persona_keywords: set[str] = set()
        if persona.interests:
            for interest in persona.interests:
                persona_keywords.update(interest.lower().split())
        if persona.tech_area:
            for area in persona.tech_area:
                persona_keywords.update(area.lower().split())
        persona_keywords -= _stopwords

        def _relevance_score(post: SocialPost) -> int:
            words = set(post.content.lower().split())
            return len(words & persona_keywords)

        # Sort by relevance + upvotes, then take top _conflicting_limit
        conflicting_sorted = sorted(
            conflicting_candidates,
            key=lambda p: (_relevance_score(p), p.upvotes),
            reverse=True,
        )
        conflicting_posts = conflicting_sorted[:_conflicting_limit]
        if conflicting_posts:
            conflicting_section = "Opinions that conflict with your perspective:\n"
            for cp in conflicting_posts:
                conflicting_section += f"- {cp.author_name}: {cp.content[:200]}\n"
            conflicting_section += "\n"
        # Highlight positive posts for highly skeptical personas to provoke counter-arguments
        # Skip in Phase 3 (synthesis) — debate escalation is no longer needed
        if persona_skepticism >= 7 and phase_ratio <= 0.66:
            positive_posts = [
                p for p in state.posts
                if getattr(p, "sentiment", "") == "positive"
                and p.author_node_id != persona.node_id
                and p.content.strip()
            ][:2]
            if positive_posts:
                conflicting_section += "Posts you may want to challenge:\n"
                for pp in positive_posts:
                    conflicting_section += f"- {pp.author_name}: {pp.content[:200]}\n"
                conflicting_section += "\n"
    # Build cross-platform context section
    if cross_platform_context:
        cross_section = (
            f"\n\nPerspectives from other platforms:\n{cross_platform_context}\n"
            f"(Consider these when forming your response, but focus on your platform's context.)"
        )
    else:
        cross_section = ""
    _region_hints = {
        "EU": "As a European user, consider GDPR/privacy implications and regulatory requirements.",
        "APAC": "As an APAC user, consider mobile-first usage patterns and price sensitivity in emerging markets.",
        "LATAM": "As a LATAM user, consider local market conditions and infrastructure constraints.",
        "MENA": "As a MENA user, consider regional compliance requirements and localization needs.",
        "NA": "",
        "Global": "",
    }
    _region_hint = _region_hints.get(getattr(persona, "region", ""), "")
    # MBTI communication style hint
    mbti_style = ""
    if persona.mbti:
        is_thinking = len(persona.mbti) >= 3 and persona.mbti[2] == 'T'
        mbti_style = (
            f"\nCommunication style ({persona.mbti}): "
            f"{'Lead with data, benchmarks, and logical consequences.' if is_thinking else 'Lead with user stories, human outcomes, and team impact.'}\n"
        )
    # ── Context Bloat 방지: 헤더/섹션/푸터 분리 + hard cap ──
    _header = (
        f"Platform: {platform.name}\n"
        f"You are {persona.name}, {persona.role} at {persona.company} "
        f"({persona.seniority}, {persona.affiliation}, age {persona.age}, {persona.generation}).\n"
        f"Interests: {', '.join(persona.interests[:5])}\n"
        f"Bias: {persona.bias_description()}\n"
        + (f"Emotional state: {persona.emotional_state}\n" if persona.emotional_state else "")
        + (f"Regional perspective: {_region_hint}\n" if _region_hint else "")
        + (mbti_style if mbti_style else "")
        + (
            "Note: your initial skepticism has somewhat softened after positive reactions from others.\n"
            if getattr(persona, "attitude_shift", 0.0) >= 0.2
            else (
                "Note: your skepticism has deepened based on the reactions you've received.\n"
                if getattr(persona, "attitude_shift", 0.0) <= -0.2
                else ""
            )
        )
        + f"Action: {action.action_type}"
        + (f" (replying to post {action.target_post_id})" if action.target_post_id else "") + "\n\n"
        f"IMPORTANT: You are NOT the creator of the idea below. You are a third-party community member reacting to someone else's product pitch.\n"
        f"Someone else's idea being discussed: {idea_text}\n\n"
    )

    # 우선순위 섹션 리스트: [MUST READ] > [CONTEXT] > [OPTIONAL]
    _sections: list[tuple[str, str]] = []
    # [MUST READ] 섹션 — 절대 생략 불가
    if prior_knowledge:
        _sections.append(("[MUST READ]", (
            f"Your domain knowledge:\n{prior_knowledge}\n"
            f"If your background knowledge mentions competing products or alternatives, reference them by name when evaluating.\n\n"
        )))
    if target_post_section:
        _sections.append(("[MUST READ]", target_post_section))
    if replies_section:
        _sections.append(("[MUST READ]", replies_section))
    # [CONTEXT] 섹션 — 공간 있으면 포함
    if history_section:
        _sections.append(("[CONTEXT]", history_section))
    if interaction_memory_section:
        _sections.append(("[CONTEXT]", interaction_memory_section))
    if cross_influence_hint:
        _sections.append(("[CONTEXT]", cross_influence_hint))
    if persona.cognitive_pattern:
        _sections.append(("[CONTEXT]", (
            f"\nCRITICAL THINKING REQUIREMENT: Your dominant thinking pattern is "
            f"'{persona.cognitive_pattern}'. You MUST visibly reflect this pattern in your response. "
            f"Frame your entire argument through this cognitive lens.\n"
        )))
    if conflicting_section:
        _sections.append(("[CONTEXT]", conflicting_section))
    # cross_section 처리 (cross_influence_hint 있으면 3줄만)
    _cross_content = (
        ("\n".join(cross_section.strip().split("\n")[:3]) + "\n")
        if cross_influence_hint and cross_section
        else (cross_section if not cross_influence_hint else "")
    )
    if _cross_content:
        _sections.append(("[CONTEXT]", _cross_content))
    # [OPTIONAL] 섹션 — 공간 부족 시 먼저 제거
    if phase_hint:
        _sections.append(("[OPTIONAL]", phase_hint))
    if bandwagon_hint:
        _sections.append(("[OPTIONAL]", f"\n{bandwagon_hint}"))
    # feed_text는 항상 [MUST READ]
    _sections.append(("[MUST READ]", f"\n{feed_text}\n\n"))

    # hard cap 적용: 우선순위 역순으로 섹션 제거
    max_prompt_chars = 4000
    _footer = (
        f"Write your {action.action_type} in {language}. Be authentic to your persona and the platform style. Do NOT claim to be the founder or creator of this idea. "
        f"If replying to a comment, directly address what that person said — agree, push back, or add nuance. "
        f"Even when posting independently, you may reference or react to opinions already visible in the feed. "
        f"Engage directly with conflicting opinions — do not ignore viewpoints that challenge your perspective.\n"
        f"You may mention other commenters by name (e.g., 'As @Name said...' or 'I disagree with @Name's point...')."
    )
    _body = "".join(content for _, content in _sections)
    if len(_header) + len(_body) + len(_footer) > max_prompt_chars:
        for priority in ("[OPTIONAL]", "[CONTEXT]"):
            while True:
                # 해당 priority 태그를 가진 섹션을 뒤에서부터 하나 제거
                _idx_to_remove = -1
                for _i in range(len(_sections) - 1, -1, -1):
                    if _sections[_i][0] == priority:
                        _idx_to_remove = _i
                        break
                if _idx_to_remove == -1:
                    break
                _sections.pop(_idx_to_remove)
                _body = "".join(content for _, content in _sections)
                if len(_header) + len(_body) + len(_footer) <= max_prompt_chars:
                    break
            if len(_header) + len(_body) + len(_footer) <= max_prompt_chars:
                break

    prompt = _header + _body + _footer
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

def _build_sim_persona_event(persona: "Persona", platform_name: str) -> dict:
    """Build a sim_persona event dict from a Persona instance."""
    return {
        "type": "sim_persona",
        "node_id": persona.node_id,
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
            "domain_type": persona.domain_type,
            "tech_area": persona.tech_area,
            "market": persona.market,
            "problem_domain": persona.problem_domain,
            "jtbd": persona.jtbd,
            "cognitive_pattern": persona.cognitive_pattern,
            "emotional_state": persona.emotional_state,
            "region": getattr(persona, "region", ""),
            "attitude_shift": getattr(persona, "attitude_shift", 0.0),
            "attitude_history": getattr(persona, "attitude_history", []),
            "interaction_ledger": getattr(persona, "interaction_ledger", {}),
            "persuasion_memory": getattr(persona, "persuasion_memory", []),
        },
        "_persona": persona,
    }


async def round_personas(
    clusters: list[dict],
    idea_text: str,
    concurrency: int = 4,
    platform_name: str = "",
    domain_info: str = "",
    competitor_context: str = "",
    pre_assigned_personas: list[dict] | None = None,
) -> AsyncGenerator[dict, None]:
    """Generate personas for all clusters for a specific platform. Yields sim_persona events.

    If `pre_assigned_personas` is provided, the fast-path is taken: personas are emitted
    directly from the pre-defined pool without any LLM calls.
    """
    # ── Fast path: use pre-assigned pool personas ─────────────────────────────
    if pre_assigned_personas is not None:
        from backend.simulation.persona_generator import persona_from_pool_entry
        cluster_count = len(clusters)
        for i, pool_entry in enumerate(pre_assigned_personas):
            # Cycle through clusters so every agent gets a knowledge context
            cluster = clusters[i % cluster_count] if cluster_count else {}
            try:
                persona = persona_from_pool_entry(pool_entry, cluster, platform_name)
                event = _build_sim_persona_event(persona, platform_name)
                event["_persona"] = persona
                yield event
            except Exception as exc:
                logger.warning(
                    "Pool persona creation failed for pool entry %d: %s",
                    i, exc,
                )
        return

    # ── Original LLM-based generation path ───────────────────────────────────
    sem = asyncio.Semaphore(concurrency)
    queue: asyncio.Queue = asyncio.Queue()
    assigned_names = sample_persona_names(len(clusters))

    # Cycle through platform-specific archetypes to enforce diversity
    arch_list = _PLATFORM_ARCHETYPES.get(platform_name, _DEFAULT_ARCHETYPES)

    async def process_one(cluster: dict, assigned_name: str, idx: int) -> None:
        forced_archetype = arch_list[idx % len(arch_list)] if arch_list else ""
        async with sem:
            try:
                persona = await generate_persona(
                    cluster,
                    idea_text=idea_text,
                    platform_name=platform_name,
                    assigned_name=assigned_name,
                    domain_info=domain_info,
                    competitor_context=competitor_context,
                    forced_archetype=forced_archetype,
                )
                await queue.put(_build_sim_persona_event(persona, platform_name))
            except Exception as exc:
                logger.warning("Persona gen failed for %s: %s", cluster.get("id", "?"), exc)
            finally:
                await queue.put(None)

    tasks = [asyncio.create_task(process_one(c, assigned_names[i], i)) for i, c in enumerate(clusters)]
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


def _compute_content_threshold(
    persona: Persona,
    round_num: int,
    total_rounds: int,
    history_len: int,
    has_unanswered_q: bool,
    has_pending_replies: bool = False,
) -> float:
    """Dynamically compute the probability of generating additional content after a vote/react action.

    Factors: persona skepticism, how much they have already spoken, round progress,
    unanswered questions, and pending replies to the agent's own posts.
    """
    base = 0.30 if getattr(persona, 'skepticism', 5) >= 7 else 0.50
    if history_len >= 3:
        base -= 0.15  # already spoken enough
    phase_ratio = round_num / max(total_rounds, 1)
    if 0.33 < phase_ratio <= 0.66:
        base += 0.05  # Phase 2: mild boost (activation_rate floor guarantees agent count)
    if phase_ratio > 0.7:
        base += 0.10  # keep participation up in later rounds
    if has_unanswered_q:
        base += 0.15  # encourage answering open questions
    if has_pending_replies:
        base += 0.20  # strongly encourage responding to replies
    upper = 0.95 if has_pending_replies else 0.80
    return max(0.10, min(upper, base))


# ── 플랫폼 라운드 ─────────────────────────────────────────────────────────────

def _extract_cross_platform_trending(
    all_platform_states: dict[str, PlatformState],
    exclude_platform: str,
    max_topics: int = 2,
    personas_map: dict[str, Persona] | None = None,
) -> str:
    """Extract trending topics/keywords from other platforms for cross-pollination.

    Returns a short text block summarizing what's hot on other platforms,
    helping break echo chambers by exposing agents to outside perspectives.
    Score includes round weight (recent rounds prioritized) and reply count.
    """
    lines: list[str] = []
    _personas = personas_map or {}
    for pname, pstate in all_platform_states.items():
        if pname == exclude_platform or not pstate.posts:
            continue
        # Build a reply count map
        reply_count: dict[str, int] = {}
        for p in pstate.posts:
            if p.parent_id is not None:
                reply_count[p.parent_id] = reply_count.get(p.parent_id, 0) + 1
        candidates = [p for p in pstate.posts if p.parent_id is None and p.author_node_id != "__seed__" and p.round_num > 0]
        # Score with round weight and reply count
        top = sorted(
            candidates,
            key=lambda p: -(
                (p.upvotes - p.downvotes)
                + p.round_num * 0.3
                + reply_count.get(p.id, 0) * 0.5
            ),
        )[:max_topics]
        if not top:
            continue
        for p in top:
            persona = _personas.get(p.author_node_id)
            role_label = persona.role if persona and persona.role else "User"
            sentiment_label = p.sentiment if p.sentiment else "neutral"
            rc = reply_count.get(p.id, 0)
            snippet = p.content[:60].replace("\n", " ")
            lines.append(f"  [{pname}] {role_label} ({sentiment_label}, {rc} replies, R{p.round_num}): {snippet}")
    if not lines:
        return ""
    return "Trending on other platforms:\n" + "\n".join(lines)


async def platform_round(
    platform: AbstractPlatform,
    state: PlatformState,
    personas: list[Persona],
    idea_text: str,
    round_num: int,
    language: str = "English",
    activation_rate: float = 0.25,
    cluster_docs_map: dict | None = None,
    total_rounds: int = 8,
    all_platform_states: dict[str, PlatformState] | None = None,
    max_concurrent: int = 10,
) -> AsyncGenerator[dict, None]:
    """Run one round for a single platform. Yields streaming events.

    Agents are processed in parallel batches (max_concurrent simultaneous LLM calls).
    Cross-platform trending topics are injected into the feed to reduce echo chambers.
    """
    # Phase ratio for adaptive guardrails
    phase_ratio = round_num / max(total_rounds, 1)
    base_activation_rate = activation_rate

    # 직전 라운드의 reply 활동을 기반으로 activation_rate 동적 조정
    if round_num > 2:
        recent_replies = sum(
            1 for p in state.posts
            if p.parent_id and getattr(p, 'round_num', round_num) == round_num - 1
        )
        older_replies = sum(
            1 for p in state.posts
            if p.parent_id and getattr(p, 'round_num', round_num) == round_num - 2
        )
        if older_replies > 0:
            ratio = recent_replies / older_replies
            if ratio >= 1.3:
                activation_rate = min(activation_rate * 1.3, 0.5)
            elif ratio <= 0.7:
                activation_rate = max(activation_rate * 0.7, 0.15)

    # Phase-based guardrails: cap/floor activation_rate per phase
    if phase_ratio <= 0.33:
        activation_rate = min(activation_rate, base_activation_rate * 1.1)
        activation_rate = min(activation_rate, 0.30)
    elif phase_ratio <= 0.66:
        activation_rate = max(activation_rate, base_activation_rate * 0.9)
    else:
        activation_rate = max(activation_rate, 0.20)

    active = select_active_agents(
        personas, activation_rate,
        recent_speakers=state.recent_speakers,
        current_round=round_num,
        posts=state.posts,
        total_rounds=total_rounds,
        mentioned_agents=getattr(state, 'mentioned_agents', None),
        phase_ratio=phase_ratio,
    )

    # ── Unanswered question priority: add responders for unanswered questions ──
    QUESTION_ACTIONS = {"ask_hn", "ask_question", "ask_advice", "ask"}
    unanswered_questions = [
        p for p in state.posts
        if p.action_type in QUESTION_ACTIONS
        and p.reply_count == 0
        and p.author_node_id != "__seed__"
    ]
    # question_hint_map: responder node_id -> hint string for unanswered questions
    question_hint_map: dict[str, str] = {}
    if unanswered_questions and len(personas) > len(active):
        personas_map_q = {p.node_id: p for p in personas}
        q_interests: set[str] = set()
        _q_hint_posts = unanswered_questions[:2]
        for q in _q_hint_posts:
            qp = personas_map_q.get(q.author_node_id)
            if qp:
                q_interests.update(getattr(qp, 'interests', []))
        active_ids = {a.node_id for a in active}
        inactive_pool = [p for p in personas if p.node_id not in active_ids]
        if q_interests:
            potential_responders = [
                p for p in inactive_pool
                if any(i in q_interests for i in getattr(p, 'interests', []))
            ][:2]
        else:
            potential_responders = inactive_pool[:2]  # fallback: no interest filter
        # Build question hint for each responder
        _q_hint_lines = []
        for q_post in _q_hint_posts:
            _q_content = (getattr(q_post, "content", "") or "")[:100]
            _q_hint_lines.append(
                f"[UNANSWERED QUESTION - prioritize replying]\nID: {q_post.id}\n\"{_q_content}\""
            )
        _combined_q_hint = "\n".join(_q_hint_lines)
        for resp in potential_responders:
            question_hint_map[resp.node_id] = _combined_q_hint
        active = list(active) + potential_responders

    # Initialize initial_emotional_state at round 1
    if round_num == 1:
        for persona in personas:
            if not persona.initial_emotional_state:
                persona.initial_emotional_state = persona.emotional_state or "neutral"

    state.round_num = round_num
    round_stats = {"active_agents": len(active), "new_posts": 0, "new_comments": 0, "new_votes": 0, "pass_count": 0}

    # Cross-platform insight: inject trending topics from other platforms
    cross_context = ""
    personas_map_cross = {p.node_id: p for p in personas}
    if all_platform_states:
        _cross_max_topics = 1 if phase_ratio > 0.66 else 2
        cross_context = _extract_cross_platform_trending(all_platform_states, platform.name, max_topics=_cross_max_topics, personas_map=personas_map_cross)

    # ── children_map 빌드: parent_id -> children 인덱스 (O(N) 1회, build_feed + 에이전트별 sibling 탐색 재사용) ──
    from collections import defaultdict as _defaultdict
    _children_idx: dict = _defaultdict(list)
    for _p in state.posts:
        _children_idx[_p.parent_id].append(_p)
    children_map_for_round: dict = dict(_children_idx)

    # ── 라운드 시작 시 피드 스냅샷 (모든 에이전트가 동일한 피드 기반으로 결정) ──
    feed_top_posts = 3 if round_num >= 3 else 5
    personas_map_feed = {p.node_id: p for p in personas}
    snapshot_feed = platform.build_feed(state, top_posts=feed_top_posts, round_num=round_num, personas_map=personas_map_feed, total_rounds=total_rounds, children_map=children_map_for_round)

    # ── Round topics hint: 이번 라운드에서 이미 다뤄진 논점 요약 (중복 방지) ──
    round_topics_hint = platform.build_round_topics_hint(state, round_num)

    # ── prior_knowledge 사전 계산 캐시: 에이전트별 _build_prior_knowledge를 1회만 호출 ──
    prior_cache: dict[str, str] = {}
    if cluster_docs_map is not None:
        _phase_ratio_prior = round_num / max(total_rounds, 1)
        _prior_top_k = 5 if _phase_ratio_prior <= 0.33 else (3 if _phase_ratio_prior <= 0.66 else 2)
        for _agent in active:
            prior_cache[_agent.node_id] = _build_prior_knowledge(
                _agent.node_id, cluster_docs_map, _agent, top_k=_prior_top_k
            )

    # ── Parallel agent processing with Semaphore ────────────────────────────
    sem = asyncio.Semaphore(max_concurrent)
    event_queue: asyncio.Queue = asyncio.Queue()

    async def process_agent(persona: Persona, round_topics_hint: str = "", children_map: dict | None = None, precomputed_prior: str = "", question_hint: str = "") -> None:
        """Process a single agent: decide action + generate content.

        Results are pushed to event_queue. Errors are caught per-agent so one
        failure doesn't abort the entire round.
        # LLM calls per agent: 1 (decide_action) + 1 (generate_content) = 2
        """
        async with sem:
            try:
                feed_text = snapshot_feed
                # Inject mention hint if this agent was @mentioned
                _mentioned_posts = getattr(state, 'mentioned_agents', {}) or {}
                _mention_post_ids = _mentioned_posts.get(persona.node_id, [])
                if _mention_post_ids:
                    for _mp_id in _mention_post_ids:
                        _mp = state.get_post(_mp_id)
                        if _mp:
                            feed_text = (
                                f"You were directly mentioned by @{_mp.author_name}. "
                                f"Consider responding to their post.\n\n"
                            ) + feed_text
                    # Clear the mention after processing
                    del _mentioned_posts[persona.node_id]
                # Append round topics hint to feed_text for generate_content (중복 논점 방지)
                if round_topics_hint:
                    feed_text = feed_text + "\n" + round_topics_hint
                # Persuasion memory context: 설득된 논거를 generate_content에 전달
                persuasion_context = ""
                if persona.persuasion_memory:
                    persuasion_context = "\n[Arguments that shifted your view]\n" + "\n".join(
                        f"- \"{s}\"" for s in persona.persuasion_memory
                    )
                if persuasion_context:
                    feed_text = feed_text + persuasion_context
                persona_history = [p for p in state.posts if p.author_node_id == persona.node_id]
                # Late Joiner 감지: 3라운드 이후 첫 참여
                is_first_participation = (len(persona_history) == 0 and round_num >= 3)
                # Sentiment fatigue hint: 동일 sentiment 3회 이상 연속 시 다양성 유도
                sentiment_fatigue_hint = ""
                if len(persona_history) >= 3:
                    recent_sentiments = [p.sentiment for p in persona_history[-3:] if p.sentiment]
                    if len(recent_sentiments) == 3 and len(set(recent_sentiments)) == 1:
                        repeated = recent_sentiments[0]
                        sentiment_fatigue_hint = (
                            f"[Perspective Check] You've expressed '{repeated}' sentiment 3 times in a row. "
                            f"Real people naturally introduce nuance -- consider a different angle or acknowledging counterpoints."
                        )
                if sentiment_fatigue_hint:
                    feed_text = feed_text + "\n" + sentiment_fatigue_hint
                my_post_ids = {p.id for p in persona_history}

                # attitude shift 계산용: 마지막 활성화 이후 새로운 리플라이만 (이중 카운팅 방지)
                last_active_round = state.recent_speakers.get(persona.node_id) if state.recent_speakers else None
                if last_active_round is None:
                    last_active_round = max((p.round_num for p in persona_history), default=0)
                new_replies_to_me = [
                    p for p in state.posts
                    if p.parent_id in my_post_ids
                    and p.author_node_id != persona.node_id
                    and p.round_num > last_active_round
                ]

                # 프롬프트 주입용: 전체 리플라이 (컨텍스트 유지)
                replies_to_me = [
                    p for p in state.posts
                    if p.parent_id in my_post_ids and p.author_node_id != persona.node_id
                ]
                # Build interaction memory: recall prior direct exchanges (Phase 2-3 only)
                interaction_memory = ""
                _phase_ratio = round_num / max(total_rounds, 1)
                if _phase_ratio > 0.33 and persona_history:
                    # Prefer interaction_ledger (populated by _update_interaction_ledger)
                    if persona.interaction_ledger:
                        _sorted_ledger = sorted(
                            persona.interaction_ledger.items(),
                            key=lambda x: -x[1].get("exchanges", 0),
                        )[:3]
                        _im_lines = []
                        for partner_id, entry in _sorted_ledger:
                            partner_persona = personas_map_feed.get(partner_id)
                            partner_name = partner_persona.name if partner_persona else partner_id
                            ex_count = entry.get("exchanges", 0)
                            agreed = entry.get("agreed_count", 0)
                            disagreed = entry.get("disagreed_count", 0)
                            _im_lines.append(
                                f"- @{partner_name} ({ex_count} exchanges, {agreed}/{disagreed} agree/disagree)"
                            )
                        if _im_lines:
                            _im_text = "Prior interactions with other participants:\n" + "\n".join(_im_lines)
                            interaction_memory = _im_text[:180]
                    else:
                        # Fallback: ad-hoc calculation from my_replies
                        my_replies = [p for p in persona_history if p.parent_id is not None]
                        if my_replies:
                            _exchanges: dict[str, list] = {}
                            for rp in my_replies:
                                parent_post = state.get_post(rp.parent_id)
                                if not parent_post or parent_post.author_node_id == persona.node_id:
                                    continue
                                cid = parent_post.author_node_id
                                _exchanges.setdefault(cid, []).append((rp, parent_post))
                            if _exchanges:
                                _sorted_partners = sorted(_exchanges.items(), key=lambda x: -len(x[1]))[:3]
                                _im_lines = []
                                for partner_id, pairs in _sorted_partners:
                                    partner_persona = personas_map_feed.get(partner_id)
                                    partner_name = partner_persona.name if partner_persona else pairs[0][1].author_name
                                    ex_count = len(pairs)
                                    _sentiments = [getattr(rp, "sentiment", "neutral") or "neutral" for rp, _ in pairs]
                                    _dominant = max(set(_sentiments), key=_sentiments.count)
                                    _their_content = pairs[-1][1].content[:30].replace(chr(10), " ")
                                    _im_lines.append(
                                        f'- @{partner_name} ({ex_count} exchanges, my tone: {_dominant}): "{_their_content}..."'
                                    )
                                if _im_lines:
                                    _im_text = "Prior interactions with other participants:\n" + "\n".join(_im_lines)
                                    interaction_memory = _im_text[:180]
                # Late Joiner hint: 늦게 참여하는 에이전트에게 맥락 힌트
                late_joiner_hint = ""
                if is_first_participation:
                    if _phase_ratio > 0.66:
                        late_joiner_hint = (
                            "[LATE JOINER] The discussion is in its final phase. "
                            "Focus on synthesis or raise an unanswered question."
                        )
                    elif _phase_ratio > 0.33:
                        late_joiner_hint = (
                            "[LATE JOINER] You're entering an ongoing debate. "
                            "Don't repeat points already made — add your unique angle."
                        )
                if late_joiner_hint:
                    feed_text = feed_text + "\n" + late_joiner_hint
                # Build compact feed for decide_action (토큰 절감: full content 대신 메타 요약)
                compact_feed = _build_compact_feed(state.posts, persona=persona, round_num=round_num, personas_map=personas_map_feed, my_post_ids=my_post_ids, children_map=children_map)
                # Information Cascade signal (Phase 1-2만)
                if _phase_ratio <= 0.66:
                    cascade_signal = _build_cascade_signal(state, round_num)
                    if cascade_signal:
                        compact_feed = cascade_signal + "\n" + compact_feed
                # Append reply candidates (underexplored threads)
                reply_candidates = platform.build_reply_candidates(state, persona, interaction_ledger=persona.interaction_ledger, personas_map=personas_map_feed, children_map=children_map)
                if reply_candidates:
                    compact_feed = compact_feed + "\n" + reply_candidates
                # Prepend mention hint to compact feed if present
                if _mention_post_ids:
                    mention_hint = feed_text[:feed_text.index(snapshot_feed)] if snapshot_feed in feed_text and feed_text != snapshot_feed else ""
                    if mention_hint:
                        compact_feed = mention_hint + compact_feed
                # Late joiner hint prepend to compact_feed for decide_action
                if late_joiner_hint and compact_feed:
                    compact_feed = late_joiner_hint + "\n" + compact_feed
                # Unanswered question hint prepend for responder agents
                if question_hint and compact_feed:
                    compact_feed = question_hint + "\n" + compact_feed
                # Retry decide_action once on LLM failure (0.5s delay)
                action = None
                for _attempt in range(2):
                    try:
                        action = await decide_action(persona, platform, compact_feed, language, round_num=round_num, total_rounds=total_rounds, persona_history=persona_history or None)
                        break
                    except LLMToolRequired:
                        raise
                    except Exception as exc:
                        if _attempt == 0:
                            logger.warning(
                                "decide_action attempt 1 failed for %s on %s: %s — retrying",
                                persona.node_id, platform.name, exc,
                            )
                            await asyncio.sleep(0.5)
                        else:
                            raise
                if action is None:
                    return

                # Handle "pass" action: agent observes but doesn't post
                if action.action_type == "pass":
                    await event_queue.put({
                        "type": "__pass_action__",
                        "_stats_key": "pass_count",
                    })
                    return

                # Validate target_post_id: prefix matching + weighted_score fallback
                seed_id = f"__seed__{platform.name}"
                if action.target_post_id is not None and state.get_post(action.target_post_id) is None:
                    # ID prefix 매칭 시도 (LLM이 truncated ID를 반환한 경우)
                    resolved = None
                    if action.target_post_id:
                        for p in state.posts:
                            if p.id.startswith(action.target_post_id) or action.target_post_id.startswith(p.id[:8]):
                                resolved = p
                                break
                    if resolved:
                        logger.info(
                            "Resolved truncated target_post_id %s -> %s",
                            action.target_post_id, resolved.id,
                        )
                        action.target_post_id = resolved.id
                    else:
                        logger.warning(
                            "Invalid target_post_id %s, using weighted_score fallback",
                            action.target_post_id,
                        )
                        # seed 집중 방지: weighted_score 상위 포스트 선택
                        candidates = [p for p in state.posts if p.id != seed_id]
                        if candidates:
                            best = max(candidates, key=lambda p: p.weighted_score or 0)
                            action.target_post_id = best.id
                        else:
                            action.target_post_id = seed_id

                # Prevent self-post targeting: fall back to weighted_score top post
                target_post = state.get_post(action.target_post_id) if action.target_post_id else None
                if target_post and target_post.author_node_id == persona.node_id:
                    candidates = [p for p in state.posts if p.id != seed_id and p.author_node_id != persona.node_id]
                    if candidates:
                        best = max(candidates, key=lambda p: p.weighted_score or 0)
                        action.target_post_id = best.id
                    else:
                        action.target_post_id = seed_id

                # Reply depth limit: max 4 levels deep
                MAX_REPLY_DEPTH = 4
                if action.action_type in ("reply", "comment") and action.target_post_id:
                    depth = 0
                    current_id = action.target_post_id
                    while current_id and depth < MAX_REPLY_DEPTH + 1:
                        p = state.get_post(current_id)
                        if not p or not p.parent_id:
                            break
                        current_id = p.parent_id
                        depth += 1
                    if depth >= MAX_REPLY_DEPTH:
                        # Move target up to reduce nesting, but stop before seed post
                        current_target = state.get_post(action.target_post_id)
                        current_depth = depth
                        while current_depth > MAX_REPLY_DEPTH and current_target and current_target.parent_id:
                            parent = state.get_post(current_target.parent_id)
                            if parent is None or parent.author_node_id == "__seed__":
                                break  # seed에 도달하기 전 중단
                            current_target = parent
                            current_depth -= 1
                        action.target_post_id = current_target.id if current_target else action.target_post_id

                # Auto-assign target_post_id for share actions with no target
                if action.action_type == "share" and action.target_post_id is None:
                    action.target_post_id = seed_id

                events: list[dict] = []

                # If the agent chose a vote/reaction action, apply it
                if not platform.requires_content(action.action_type) and action.target_post_id:
                    async with state._write_lock:
                        updated = platform.update_vote_counts(state, action.target_post_id, action.action_type, round_num=round_num, voter_node_id=persona.node_id, seniority=persona.seniority, personas_map=personas_map_feed)
                    events.append({
                        "type": "sim_platform_reaction",
                        "platform": platform.name,
                        "post_id": action.target_post_id,
                        "reaction_type": action.action_type,
                        "actor_name": persona.name,
                        "new_upvotes": updated.upvotes if updated else 0,
                        "new_downvotes": updated.downvotes if updated else 0,
                        "_stats_key": "new_votes",
                    })

                # Generate a content post/comment (gated for no-content actions)
                allowed = platform.get_allowed_actions(persona)
                content_actions = [a for a in allowed if platform.requires_content(a)]
                # If the agent chose a no-content action (upvote/react), gate additional content generation
                should_generate_content = True
                if not platform.requires_content(action.action_type):
                    # Dynamic threshold based on persona traits, round progress, history, and unanswered questions
                    _history_len = len(persona_history) if persona_history else 0
                    _has_unanswered_q = any(
                        p.action_type in ("ask_hn", "ask_question", "ask_advice", "ask")
                        and p.reply_count == 0
                        and p.author_node_id != "__seed__"
                        for p in state.posts
                    )
                    threshold = _compute_content_threshold(
                        persona, round_num, total_rounds, _history_len, _has_unanswered_q,
                        has_pending_replies=bool(new_replies_to_me),
                    )
                    should_generate_content = random.random() < threshold
                if content_actions and should_generate_content:
                    content_action = action if platform.requires_content(action.action_type) else \
                        AgentAction(action_type=content_actions[0], target_post_id=action.target_post_id)
                    # Retry generate_content once on LLM failure (0.5s delay)
                    content = None
                    structured_data = {}
                    for _attempt in range(2):
                        try:
                            content, structured_data = await generate_content(
                                persona, content_action, platform, feed_text, idea_text, language,
                                cluster_docs_map=cluster_docs_map,
                                persona_history=persona_history or None,
                                replies_to_me=replies_to_me or None,
                                state=state,
                                cross_platform_context=cross_context,
                                round_num=round_num,
                                total_rounds=total_rounds,
                                interaction_memory=interaction_memory,
                                children_map=children_map,
                                precomputed_prior=precomputed_prior,
                            )
                            break
                        except LLMToolRequired:
                            raise
                        except Exception as exc:
                            if _attempt == 0:
                                logger.warning(
                                    "generate_content attempt 1 failed for %s on %s: %s — retrying",
                                    persona.node_id, platform.name, exc,
                                )
                                await asyncio.sleep(0.5)
                            else:
                                raise
                    if content is None:
                        # Both attempts failed silently; skip content creation
                        content = f"[{persona.name}] Interesting idea."
                        structured_data = {}

                    # ── 반복/저품질 콘텐츠 필터링 ──
                    # 길이 검사
                    if len(content.strip()) < 25:
                        for ev in events:
                            await event_queue.put(ev)
                        return

                    # 자기 반복 검사: persona_history 최근 3개와 비교
                    recent_own = [h.content for h in persona_history[-3:]] if persona_history else []
                    _skip_content = False
                    for prev in recent_own:
                        if SequenceMatcher(None, content[:200], prev[:200]).ratio() > 0.7:
                            _skip_content = True
                            break
                    if _skip_content:
                        for ev in events:
                            await event_queue.put(ev)
                        return

                    # Cross-agent similarity check: compare with recent posts from this round
                    recent_round_posts = [
                        p for p in state.posts
                        if getattr(p, 'round_num', 0) == round_num
                    ][-5:]
                    for rp in recent_round_posts:
                        if rp.content and SequenceMatcher(None, content[:200], rp.content[:200]).ratio() > 0.65:
                            _skip_content = True
                            break
                    if _skip_content:
                        for ev in events:
                            await event_queue.put(ev)
                        return

                    # 창작자 자처 콘텐츠 필터: 에이전트가 제품 창작자인 척 하는 콘텐츠 스킵
                    if _is_creator_impersonation(content):
                        for ev in events:
                            await event_queue.put(ev)
                        return

                    # new_post actions are always top-level (no parent)
                    effective_parent_id = None if content_action.action_type == "new_post" else content_action.target_post_id
                    validated_sentiment = _validate_sentiment(content, structured_data.get("sentiment", "neutral"))
                    post = SocialPost(
                        id=str(uuid.uuid4()),
                        platform=platform.name,
                        author_node_id=persona.node_id,
                        author_name=persona.name,
                        content=content,
                        action_type=content_action.action_type,
                        round_num=round_num,
                        parent_id=effective_parent_id,
                        structured_data=structured_data,
                        sentiment=validated_sentiment,
                    )
                    # Extract @Name mentions from content
                    mentions = re.findall(r"@(\w[\w ]*\w|\w)", post.content)
                    if mentions:
                        post.structured_data["mentions"] = mentions
                    # Save mentioned agent node_ids for priority activation next round
                    mention_names = structured_data.get("mentions", []) or mentions
                    name_to_node = {p.name.lower(): p.node_id for p in personas} if mention_names else {}
                    # ── Lock-protected PlatformState mutation ──
                    async with state._write_lock:
                        if mention_names:
                            for mname in mention_names:
                                target_nid = name_to_node.get(mname.lower())
                                if target_nid and target_nid != persona.node_id:
                                    if not hasattr(state, 'mentioned_agents') or state.mentioned_agents is None:
                                        state.mentioned_agents = {}
                                    state.mentioned_agents.setdefault(target_nid, []).append(post.id)
                        state.add_post(post)
                        _update_interaction_ledger(persona, post, state, personas_map_feed)
                        # Increment parent's reply_count for feed display
                        if post.parent_id:
                            parent = state.get_post(post.parent_id)
                            if parent is not None:
                                parent.reply_count += 1
                        state.recent_speakers[persona.node_id] = round_num
                    stats_key = "new_comments" if content_action.target_post_id else "new_posts"
                    events.append({
                        "type": "sim_platform_post",
                        "platform": platform.name,
                        "post": dataclasses.asdict(post),
                        "_stats_key": stats_key,
                    })

                # Attitude shift: adjust based on sentiment of replies received
                # Seniority weights for reply influence (higher seniority = more persuasive)
                _SR_W = {'c_suite': 1.8, 'vp': 1.6, 'director': 1.5, 'principal': 1.4,
                         'lead': 1.3, 'senior': 1.2, 'mid': 1.0, 'junior': 0.8, 'intern': 0.6}
                _local_pmap = {p.node_id: p for p in personas}
                if new_replies_to_me:
                    pos = sum(1 for r in new_replies_to_me if getattr(r, "sentiment", "") == "positive")
                    neg = sum(1 for r in new_replies_to_me if getattr(r, "sentiment", "") == "negative")
                    constructive = sum(1 for r in new_replies_to_me if getattr(r, "sentiment", "") == "constructive")
                    total = pos + neg + constructive
                    delta = 0.0
                    reply_delta = 0.0  # reply 기반 delta만 별도 추적 (cascade 계산용)
                    trigger_post_id = new_replies_to_me[-1].id if new_replies_to_me else ""
                    # skepticism-based resistance: higher skepticism = more resistant to attitude change
                    # skepticism=10 -> resistance=0.65, skepticism=5 -> 1.0, skepticism=1 -> 1.28 (capped at 0.3 minimum)
                    resistance = max(0.3, 1.0 - (persona.skepticism - 5) * 0.07)
                    # Adaptive resistance decay: repeated persuasion in same direction lowers resistance
                    _history = getattr(persona, 'attitude_history', []) or []
                    _consec = 0
                    if _history:
                        _last_sign = 1 if _history[-1].get('delta', 0) > 0 else -1
                        for _h in reversed(_history):
                            _d = _h.get('delta', 0)
                            if (_d > 0 and _last_sign > 0) or (_d < 0 and _last_sign < 0):
                                _consec += 1
                            else:
                                break
                    if _consec >= 5:
                        resistance *= 0.70
                    elif _consec >= 3:
                        resistance *= 0.85
                    def _reply_weight(r) -> float:
                        """seniority + in-group 보정 가중치 * argument quality."""
                        author = _local_pmap.get(r.author_node_id)
                        w = _SR_W.get(getattr(author, 'seniority', 'mid') or 'mid', 1.0)
                        # in-group 보정: 같은 domain_type이면 동료 의견이 더 설득적 (1.2배)
                        if author and (getattr(author, 'domain_type', '') or '') == (getattr(persona, 'domain_type', '') or '') != '':
                            w *= 1.2
                        return w * _compute_argument_quality(r)

                    if total > 0:
                        if pos / total > 0.6:
                            _pos_weight = sum(_reply_weight(r) for r in new_replies_to_me if getattr(r, "sentiment", "") == "positive") / max(pos, 1)
                            if pos > 1:
                                _pos_weight *= min(1.0 + (pos - 1) * 0.15, 1.6)
                            _d = 0.05 * resistance * min(_pos_weight, 2.0)
                            reply_delta = _d
                            delta = _d
                            persona.attitude_shift = max(-1.0, min(1.0, persona.attitude_shift + _d))
                        elif neg / total > 0.6:
                            _neg_weight = sum(_reply_weight(r) for r in new_replies_to_me if getattr(r, "sentiment", "") == "negative") / max(neg, 1)
                            if neg > 1:
                                _neg_weight *= min(1.0 + (neg - 1) * 0.15, 1.6)
                            _d = -0.05 * resistance * min(_neg_weight, 2.0)
                            reply_delta = _d
                            delta = _d
                            persona.attitude_shift = max(-1.0, min(1.0, persona.attitude_shift + _d))
                    # Constructive sentiment: weak positive nudge (also resistance-adjusted, seniority-weighted)
                    if constructive > 0:
                        _constructive_weight_sum = sum(_reply_weight(r) for r in new_replies_to_me if getattr(r, "sentiment", "") == "constructive")
                        constructive_delta = 0.02 * resistance * _constructive_weight_sum / max(constructive, 1)
                        delta += constructive_delta
                        persona.attitude_shift = max(-1.0, min(1.0, persona.attitude_shift + constructive_delta))

                    # 내 포스트에 달린 vote 반응 반영 (reply보다 약하게)
                    my_posts = [p for p in state.posts if p.author_node_id == persona.node_id and getattr(p, 'round_num', 0) == round_num - 1]
                    net_votes = sum(p.upvotes - p.downvotes for p in my_posts)
                    if net_votes > 2:
                        vote_delta = 0.02 * resistance
                        delta += vote_delta
                        persona.attitude_shift = max(-1.0, min(1.0, persona.attitude_shift + vote_delta))
                    elif net_votes < -2:
                        vote_delta = -0.02 * resistance
                        delta += vote_delta
                        persona.attitude_shift = max(-1.0, min(1.0, persona.attitude_shift + vote_delta))

                    # Endorsement boost: 내 포스트가 시니어에게 endorsed된 경우 attitude boost
                    endorsement_boost = 0.0
                    for mp in my_posts:
                        n_endorsers = len(getattr(mp, 'endorsed_by', []))
                        if n_endorsers > 0:
                            endorsement_boost += min(n_endorsers * 0.02, 0.04)  # 최대 0.04 cap
                    if endorsement_boost > 0:
                        delta += endorsement_boost
                        persona.attitude_shift = max(-1.0, min(1.0, persona.attitude_shift + endorsement_boost))

                    # Early round cascade amplification (Phase 1에서만, skepticism < 6)
                    if _phase_ratio <= 0.33 and getattr(persona, 'skepticism', 5) < 6:
                        cascade_extra = reply_delta * 0.5  # reply delta 기반 cascade (double-counting 방지)
                        delta += cascade_extra
                        persona.attitude_shift = max(-1.0, min(1.0, persona.attitude_shift + cascade_extra))

                    if delta != 0.0:
                        persona.attitude_history.append({
                            "round": round_num,
                            "delta": delta,
                            "trigger_post_id": trigger_post_id,
                        })
                        _update_emotional_state(persona)

                        # Persuasion memory: 설득력 있는 논거 기억 (|delta| >= 0.03)
                        if abs(delta) >= 0.03 and new_replies_to_me:
                            _trigger_post = new_replies_to_me[-1]
                            snippet = (_trigger_post.content or "")[:80]
                            if snippet and snippet not in persona.persuasion_memory:
                                persona.persuasion_memory.append(snippet)
                                if len(persona.persuasion_memory) > 3:
                                    persona.persuasion_memory.pop(0)  # FIFO, 최대 3개

                # Passive exposure: feed dominant sentiment nudges attitude when opposing
                if compact_feed:
                    _feed_posts_for_exposure = [
                        p for p in state.posts
                        if p.round_num == round_num and p.author_node_id != persona.node_id
                    ]
                    _exp_pos = sum(1 for p in _feed_posts_for_exposure if p.sentiment == "positive")
                    _exp_neg = sum(1 for p in _feed_posts_for_exposure if p.sentiment == "negative")
                    _exp_total = max(_exp_pos + _exp_neg, 1)
                    _exp_ratio = abs(_exp_pos - _exp_neg) / _exp_total
                    # skepticism >= 8: immune to passive exposure
                    if _exp_ratio > 0.4 and getattr(persona, "skepticism", 5) < 8:
                        _passive_resistance = max(0.3, 1.0 - (persona.skepticism - 5) * 0.07)
                        _dominant_positive = _exp_pos > _exp_neg
                        _current_positive = getattr(persona, "attitude_shift", 0.0) >= 0
                        if _dominant_positive != _current_positive:  # opposite direction only
                            _exposure_delta = 0.01 * _passive_resistance * (_exp_ratio - 0.4) * 2.5
                            _exposure_delta = _exposure_delta if _dominant_positive else -_exposure_delta
                            persona.attitude_shift = max(-1.0, min(1.0, persona.attitude_shift + _exposure_delta))
                            if abs(_exposure_delta) > 0.001:
                                persona.attitude_history.append({
                                    "round": round_num,
                                    "delta": round(_exposure_delta, 4),
                                    "trigger_post_id": "__passive_exposure__",
                                })
                                _update_emotional_state(persona)

                # Late Joiner conformity bias: 기존 dominant sentiment 방향으로 초기 nudge
                if is_first_participation:
                    current_posts = [p for p in state.posts if p.round_num == round_num]
                    if current_posts:
                        from collections import Counter as _C2
                        sents = [p.sentiment for p in current_posts if p.sentiment]
                        if sents:
                            dom, dom_count = _C2(sents).most_common(1)[0]
                            dom_ratio = dom_count / len(sents)
                            if dom_ratio > 0.5:
                                _pos_sents = {'positive', 'constructive'}
                                nudge = 0.03 if dom in _pos_sents else -0.03
                                persona.attitude_shift = max(-1.0, min(1.0, persona.attitude_shift + nudge))
                                persona.attitude_history.append({
                                    "round": round_num,
                                    "delta": nudge,
                                    "trigger_post_id": "__late_joiner_conformity__",
                                })

                for ev in events:
                    await event_queue.put(ev)
            except Exception as exc:
                logger.warning(
                    "Agent %s failed on %s round %d: %s",
                    persona.node_id, platform.name, round_num, exc,
                )
            finally:
                await event_queue.put(None)  # sentinel

    tasks = [asyncio.create_task(process_agent(p, round_topics_hint=round_topics_hint, children_map=children_map_for_round, precomputed_prior=prior_cache.get(p.node_id, ""), question_hint=question_hint_map.get(p.node_id, ""))) for p in active]
    remaining = len(tasks)
    while remaining > 0:
        item = await event_queue.get()
        if item is None:
            remaining -= 1
        else:
            stats_key = item.pop("_stats_key", None)
            if stats_key:
                round_stats[stats_key] = round_stats.get(stats_key, 0) + 1
            # Internal-only events (e.g. pass tracking) are not yielded
            if item.get("type", "").startswith("__"):
                continue
            yield item

    # 해당 라운드에서 활동한 에이전트들의 segment 분포 계산
    personas_map = {p.node_id: p for p in personas}
    round_posts = [p for p in state.posts if getattr(p, 'round_num', 0) == round_num and p.author_node_id != "__seed__"]
    seg_dist: dict[str, int] = {}
    for post in round_posts:
        persona_obj = personas_map.get(post.author_node_id)
        if persona_obj:
            seg = _classify_segment(persona_obj)
            seg_dist[seg] = seg_dist.get(seg, 0) + 1
    round_stats["segment_distribution"] = seg_dist

    action_dist = {}
    for post in round_posts:
        at = post.action_type or "unknown"
        action_dist[at] = action_dist.get(at, 0) + 1
    round_stats["action_type_distribution"] = action_dist

    # inactive = 전체 에이전트 - 실제 활동한 에이전트 (pass_count is tracked via event queue)
    active_node_ids = {post.author_node_id for post in round_posts}
    round_stats["inactive_count"] = len(personas) - len(active_node_ids)
    round_stats["adjusted_activation_rate"] = activation_rate

    # sentiment_distribution 집계 (seed 포스트 제외)
    _sent_dist: dict[str, int] = {"positive": 0, "neutral": 0, "negative": 0}
    for _rp in round_posts:
        _s = getattr(_rp, "sentiment", None) or "neutral"
        _s_lower = _s.lower()
        if _s_lower in _sent_dist:
            _sent_dist[_s_lower] += 1
        else:
            _sent_dist["neutral"] += 1
    round_stats["sentiment_distribution"] = _sent_dist

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
                    "description": "Include all 10 segment types",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {
                                "type": "string",
                                "enum": ["developer", "investor", "early_adopter", "skeptic", "pm", "founder", "executive", "designer", "marketer", "analyst"],
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
                    "minItems": 3,
                    "maxItems": 10,
                },
                "praise_clusters": {
                    "type": "array",
                    "description": "Top recurring praise themes and what people liked",
                    "minItems": 2,
                    "maxItems": 4,
                    "items": {
                        "type": "object",
                        "properties": {
                            "theme": {"type": "string", "description": "What aspect people praised"},
                            "count": {"type": "integer", "description": "Approximate number of positive mentions"},
                            "examples": {
                                "type": "array",
                                "items": {"type": "string"},
                                "maxItems": 2,
                                "description": "1-2 direct quote examples",
                            },
                        },
                        "required": ["theme", "count", "examples"],
                    },
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
                "key_debates": {
                    "type": "array",
                    "description": "2-3 key debates where agents strongly disagreed",
                    "items": {
                        "type": "object",
                        "properties": {
                            "topic": {"type": "string", "description": "What the debate was about"},
                            "for_arguments": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Main arguments in favor",
                            },
                            "against_arguments": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Main arguments against",
                            },
                            "resolution": {
                                "type": "string",
                                "description": "How the debate was resolved, or note that it remains contested",
                            },
                        },
                        "required": ["topic", "for_arguments", "against_arguments", "resolution"],
                    },
                    "minItems": 2,
                    "maxItems": 3,
                },
                "next_steps": {
                    "type": "array",
                    "description": "Top 3-5 prioritized actions the product team should take based on simulation evidence",
                    "items": {
                        "type": "object",
                        "properties": {
                            "priority": {"type": "string", "enum": ["P0", "P1", "P2"], "description": "P0=critical/immediate, P1=important/near-term, P2=nice-to-have"},
                            "action": {"type": "string", "description": "Specific, concrete action to take (1-2 sentences)"},
                            "rationale": {"type": "string", "description": "Evidence-based rationale from simulation data (1-2 sentences)"},
                            "segment_impact": {"type": "array", "items": {"type": "string"}, "description": "Segment names most impacted by this action"},
                        },
                        "required": ["priority", "action", "rationale", "segment_impact"],
                    },
                    "minItems": 2,
                    "maxItems": 5,
                },
            },
            "required": ["verdict", "evidence_count", "segments", "praise_clusters", "criticism_clusters", "improvements", "key_debates", "next_steps"],
        },
    },
}


def _classify_segment(persona: "Persona") -> str:
    """Classify a persona into a market segment based on role, affiliation, and bias scores."""
    role_lower = (getattr(persona, "role", "") or "").lower()
    affil_lower = (getattr(persona, "affiliation", "") or "").lower()
    combined = f"{role_lower} {affil_lower}"
    skepticism_val = getattr(persona, "skepticism", None) or 5
    commercial_val = getattr(persona, "commercial_focus", None) or 5
    innovation_val = getattr(persona, "innovation_openness", None) or 5

    # 1. Role contains investor keywords → investor
    investor_keywords = ("invest", "vc", "venture capital", "fund", "angel investor", "angel")
    if any(kw in role_lower for kw in investor_keywords):
        return "investor"
    # 2. High commercial focus AND role contains investor keywords → investor
    if commercial_val >= 8 and any(kw in role_lower for kw in investor_keywords):
        return "investor"
    # 2.5. Seniority-based executive: director/vp/c_suite prioritized over skepticism
    if (getattr(persona, 'seniority', '') or '').lower().strip() in ('director', 'vp', 'c_suite'):
        # investor keywords still take priority (role-based)
        if any(k in role_lower for k in ("investor", "vc ", "venture", "angel", "partner")):
            return "investor"
        return "executive"
    # 3. High skepticism → skeptic
    if skepticism_val >= 7:
        return "skeptic"
    # 4. High innovation openness AND low skepticism → early_adopter
    if innovation_val >= 7 and skepticism_val <= 3:
        return "early_adopter"
    # 5. PM roles
    if any(kw in role_lower for kw in ("pm", "product manager", "product director")):
        return "pm"
    # 6. Developer roles
    if any(kw in role_lower for kw in ("dev", "engineer", "architect", "sre", "devops", "programmer", "coder", "swe")):
        return "developer"
    # 7. Founder roles
    if any(kw in role_lower for kw in ("founder", "co-founder", "entrepreneur", "startup")):
        return "founder"
    # 8. Executive roles
    if any(kw in role_lower for kw in ("ceo", "cto", "coo", "cfo", "chief", "president", "vp", "vice president")):
        return "executive"
    # 9. Designer roles
    if any(kw in role_lower for kw in ("design", "designer", "ux", "ui designer", "product designer", "ui", "creative")):
        return "designer"
    # 10. Marketer roles
    if any(kw in role_lower for kw in ("market", "marketing", "growth", "brand", "seo", "content strateg")):
        return "marketer"
    # 11. Analyst / researcher / academic roles
    if any(kw in role_lower for kw in ("analyst", "researcher", "scientist", "professor", "academic", "consultant", "advisor", "economist", "strategist", "research analyst", "market analyst")):
        return "analyst"
    if affil_lower == "academic":
        return "analyst"
    # 12. Fallback: affiliation/role based
    if any(kw in combined for kw in ("developer", "engineer", "dev")):
        return "developer"
    if any(kw in combined for kw in ("investor", "vc", "fund")):
        return "investor"
    if any(kw in combined for kw in ("early", "adopter", "user")):
        return "early_adopter"
    if any(kw in combined for kw in ("skeptic", "critic")):
        return "skeptic"
    if any(kw in combined for kw in ("pm", "product")):
        return "pm"
    return "other"


def _format_author(post: "SocialPost", persona_map: dict[str, "Persona"]) -> str:
    """Format author label with role/affiliation metadata when persona is available."""
    persona = persona_map.get(post.author_node_id)
    if persona is not None:
        return f"{persona.name} ({persona.role}, {persona.affiliation})"
    return post.author_name


def _validate_report(report_json: dict, total_posts: int, adoption_score: float) -> dict:
    """LLM 생성 리포트 필드 자동 검증 및 교정"""
    corrections = []

    # 검증 1: evidence_count 교정
    actual_evidence = total_posts
    reported_evidence = report_json.get("evidence_count", 0)
    if reported_evidence > 0 and abs(reported_evidence - actual_evidence) / max(actual_evidence, 1) > 0.2:
        report_json["evidence_count"] = actual_evidence
        corrections.append(f"evidence_count corrected: {reported_evidence} -> {actual_evidence}")

    # 검증 2: verdict vs adoption_score 정합성
    verdict = report_json.get("verdict", "mixed")
    if adoption_score >= 70 and verdict in ("negative", "skeptical"):
        report_json["verdict"] = "mixed"
        corrections.append(f"verdict corrected: {verdict} -> mixed (adoption_score={adoption_score:.1f})")
    elif adoption_score <= 30 and verdict in ("positive",):
        report_json["verdict"] = "mixed"
        corrections.append(f"verdict corrected: {verdict} -> mixed (adoption_score={adoption_score:.1f})")

    # 검증 3: improvements frequency 합 교정
    improvements = report_json.get("improvements", [])
    if improvements:
        freq_sum = sum(imp.get("frequency", 0) for imp in improvements)
        if actual_evidence > 0 and freq_sum > actual_evidence * 1.5:
            scale = (actual_evidence * 1.5) / freq_sum
            for imp in improvements:
                imp["frequency"] = max(1, int(imp.get("frequency", 0) * scale))
            corrections.append(f"improvements frequency scaled down by {scale:.2f}")

    report_json["validation"] = {
        "corrections_applied": len(corrections),
        "details": corrections,
    }
    return report_json


async def generate_report(
    platform_states: list,
    idea_text: str,
    domain: str,
    language: str = "English",
    personas: dict[str, "Persona"] | None = None,
    round_segment_distributions: dict | None = None,
    round_action_type_distributions: dict | None = None,
    total_agent_count: int = 0,
    convergence_round: int | None = None,
    round_pass_counts: dict | None = None,
    round_inactive_counts: dict | None = None,
) -> tuple[dict, str]:
    """Returns (report_json, report_md)."""
    platform_summaries = []
    total_evidence = 0
    shown_post_ids: set[str] = set()  # track top-5 upvote posts shown per platform (for debated threads dedup)
    for state in platform_states:
        posts = state.posts
        total_evidence += sum(
            1 for p in posts
            if p.author_node_id != "__seed__" and p.content.strip()
        )
        top_posts = sorted(
            [p for p in posts if p.parent_id is None],
            key=lambda p: -p.upvotes
        )[:5]
        shown_post_ids.update(p.id for p in top_posts)

        # Build comment index: parent_id -> list of replies (sorted by upvotes)
        comments_by_parent: dict[str, list] = {}
        for p in posts:
            if p.parent_id is not None:
                comments_by_parent.setdefault(p.parent_id, []).append(p)
        for clist in comments_by_parent.values():
            clist.sort(key=lambda c: -c.upvotes)

        # Format top posts with nested discussions
        discussions_lines: list[str] = []
        persona_map = personas or {}
        for p in top_posts:
            author_label = _format_author(p, persona_map)
            discussions_lines.append(
                f"  [{p.upvotes}↑] {author_label}: {p.content[:200]}"
            )
            # Attach up to 3 top comments per post, truncated to 200 chars
            top_comments = comments_by_parent.get(p.id, [])[:3]
            for c in top_comments:
                comment_author = _format_author(c, persona_map)
                discussions_lines.append(
                    f"    ↳ [{c.upvotes}↑] {comment_author}: {c.content[:200]}"
                )

        discussions_text = "\n".join(discussions_lines)
        platform_summaries.append(
            f"### {state.platform_name}\n"
            f"Posts: {len([p for p in posts if p.parent_id is None])}, "
            f"Comments: {len([p for p in posts if p.parent_id is not None])}\n"
            f"Discussions:\n{discussions_text}"
        )

    # Build participant demographics section from personas
    demographics_section = ""
    if personas:
        from collections import Counter
        persona_list = list(personas.values())
        n = len(persona_list)
        if n > 0:
            seniority_dist = Counter(getattr(p, 'seniority', 'unknown') for p in persona_list)
            affiliation_dist = Counter(getattr(p, 'affiliation', 'unknown') for p in persona_list)
            avg_skepticism = sum(getattr(p, 'skepticism', 5) for p in persona_list) / n
            avg_commercial = sum(getattr(p, 'commercial_focus', 5) for p in persona_list) / n
            avg_innovation = sum(getattr(p, 'innovation_openness', 5) for p in persona_list) / n
            seniority_str = ", ".join(f"{k}: {v}" for k, v in seniority_dist.most_common(5))
            affiliation_str = ", ".join(f"{k}: {v}" for k, v in affiliation_dist.most_common(5))
            demographics_section = (
                f"\nParticipant Demographics ({n} personas):\n"
                f"  Seniority: {seniority_str}\n"
                f"  Affiliation: {affiliation_str}\n"
                f"  Avg skepticism: {avg_skepticism:.1f}/10, commercial_focus: {avg_commercial:.1f}/10, innovation_openness: {avg_innovation:.1f}/10\n"
            )

    # Pre-compute statistics for the prompt
    from collections import Counter as _Counter
    _platform_stats_lines: list[str] = []
    _agent_post_counter: _Counter = _Counter()
    for state in platform_states:
        posts = state.posts
        _plat_total = sum(1 for p in posts if p.author_node_id != "__seed__" and p.content.strip())
        _sent_counts: dict[str, int] = {"positive": 0, "negative": 0, "constructive": 0, "neutral": 0}
        for p in posts:
            if p.author_node_id == "__seed__":
                continue
            s = getattr(p, "sentiment", "") or ""
            if s in _sent_counts:
                _sent_counts[s] += 1
            _agent_post_counter[p.author_node_id] += 1
        if _plat_total > 0:
            _pct = lambda v: f"{v / _plat_total * 100:.0f}%"
            _platform_stats_lines.append(
                f"  {state.platform_name}: total={_plat_total}, "
                f"positive={_pct(_sent_counts['positive'])}, "
                f"negative={_pct(_sent_counts['negative'])}, "
                f"constructive={_pct(_sent_counts['constructive'])}"
            )
        else:
            _platform_stats_lines.append(f"  {state.platform_name}: total=0")
    _top_agents = _agent_post_counter.most_common(5)
    _top_agents_str = ", ".join(f"{node_id}: {count} posts" for node_id, count in _top_agents)
    precomputed_block = (
        f"\n=== PRE-COMPUTED STATISTICS (use these exact numbers, do not recalculate) ===\n"
        f"Total evidence posts: {total_evidence}\n"
        f"Platform breakdown:\n"
        + "\n".join(_platform_stats_lines)
        + f"\nTop active agents: {_top_agents_str}\n"
    )

    # ── Round-by-round highlights: top positive + top negative per round ──
    all_non_seed = [p for state in platform_states for p in state.posts if p.author_node_id != "__seed__"]
    rounds = sorted(set(p.round_num for p in all_non_seed))
    round_summary_lines: list[str] = []
    for rn in rounds:
        rnd_posts = [p for p in all_non_seed if p.round_num == rn]
        top_pos = max(rnd_posts, key=lambda p: p.upvotes - p.downvotes, default=None)
        top_neg = max(
            (p for p in rnd_posts if getattr(p, 'sentiment', '') == 'negative'),
            key=lambda p: p.upvotes, default=None,
        )
        if top_pos:
            round_summary_lines.append(f"R{rn} top: [{top_pos.platform}] {top_pos.author_name}: {top_pos.content[:150]}")
        if top_neg and top_neg.id != (top_pos.id if top_pos else None):
            round_summary_lines.append(f"R{rn} critical: [{top_neg.platform}] {top_neg.author_name}: {top_neg.content[:150]}")
    if round_summary_lines:
        precomputed_block += "\n\nRound-by-round highlights:\n" + "\n".join(round_summary_lines[:20])

    # ── Pre-aggregated keyword themes (stopwords excluded) ──
    import re as _re
    _STOPWORDS = {"the","a","is","and","of","to","in","it","for","this","that","but","with","are","was","be","not","i","we","you","have","they","on","at","by","an","or","as","so","if","my","your","our","its"}
    _neg_words: _Counter = _Counter()
    _pos_words: _Counter = _Counter()
    for p in all_non_seed:
        words = [w.lower() for w in _re.findall(r'\b[a-z]{3,}\b', p.content) if w.lower() not in _STOPWORDS]
        if getattr(p, 'sentiment', '') == 'negative':
            _neg_words.update(words)
        elif getattr(p, 'sentiment', '') == 'positive':
            _pos_words.update(words)
    if _neg_words:
        precomputed_block += f"\n\nFrequent criticism keywords: {', '.join(w for w, _ in _neg_words.most_common(10))}"
    if _pos_words:
        precomputed_block += f"\n\nFrequent praise keywords: {', '.join(w for w, _ in _pos_words.most_common(10))}"

    # Attitude shift 요약 빌드
    if personas:
        attitude_lines = []
        all_personas_list = list(personas.values())
        top_shifted = sorted(
            [p for p in all_personas_list if hasattr(p, 'attitude_shift') and p.attitude_shift],
            key=lambda p: abs(p.attitude_shift or 0),
            reverse=True,
        )[:8]
        for p in top_shifted:
            if abs(p.attitude_shift or 0) > 0.05:
                shift_str = f"{p.attitude_shift:+.2f}" if p.attitude_shift else "0.00"
                initial = getattr(p, 'initial_emotional_state', None) or getattr(p, 'emotional_state', None) or "unknown"
                current = getattr(p, 'emotional_state', None) or "unknown"
                seg = _classify_segment(p)
                attitude_lines.append(f"- {p.name} ({p.role}, {seg}): {shift_str} | {initial} -> {current}")

        # segment별 평균 attitude shift
        seg_shifts_pre: dict[str, list[float]] = {}
        for p in all_personas_list:
            seg = _classify_segment(p)
            shift_val = getattr(p, 'attitude_shift', None)
            if shift_val:
                seg_shifts_pre.setdefault(seg, []).append(shift_val)
        seg_shift_lines = []
        for seg, shifts in seg_shifts_pre.items():
            avg = sum(shifts) / len(shifts)
            shifted = sum(1 for s in shifts if abs(s) > 0.05)
            seg_shift_lines.append(f"- {seg}: avg {avg:+.2f} ({shifted} of {len(shifts)} shifted)")

        if attitude_lines:
            precomputed_block += "\n\nAttitude shifts observed:\n" + "\n".join(attitude_lines)
        if seg_shift_lines:
            precomputed_block += "\n\nSegment attitude trends:\n" + "\n".join(seg_shift_lines)

    # ── 세그먼트별 대표 포스트 원문 증거 빌드 ──
    # all_personas_map은 아래 region_sentiment 섹션에서 정의되므로 여기서는
    # personas 인자를 직접 사용
    _seg_personas_map: dict[str, Persona] = dict(personas) if personas else {}
    seg_evidence: dict[str, list[str]] = {}
    for post in all_non_seed:
        persona_obj_se = _seg_personas_map.get(post.author_node_id)
        if not persona_obj_se:
            continue
        seg = _classify_segment(persona_obj_se)
        if seg not in seg_evidence:
            seg_evidence[seg] = []
        if len(seg_evidence[seg]) < 2:  # 세그먼트당 최대 2개
            seg_evidence[seg].append(f'"{post.content[:180]}" \u2013{post.author_name}')

    if seg_evidence:
        precomputed_block += "\n\nSegment evidence (verbatim quotes per segment):\n"
        for seg, quotes in seg_evidence.items():
            precomputed_block += f"  {seg}: " + " | ".join(quotes) + "\n"

    # ── Unanswered questions: question-type posts with zero replies ──
    _QUESTION_ACTIONS = {"ask_hn", "ask_question", "ask_advice", "question", "ask"}
    _unanswered = [
        p for state in platform_states for p in state.posts
        if p.action_type in _QUESTION_ACTIONS and p.reply_count == 0 and p.author_node_id != "__seed__"
    ][:5]
    if _unanswered:
        precomputed_block += "\n\nUnanswered questions (consider in next_steps/key_debates):\n"
        for uq in _unanswered:
            snippet = uq.content[:90].replace("\n", " ")
            precomputed_block += f"- [{uq.platform}] @{uq.author_name}: {snippet}\n"

    # Most debated threads (by reply count, excluding already shown top-5 upvote posts)
    _all_report_posts = [p for state in platform_states for p in state.posts if p.author_node_id != "__seed__"]
    debated = sorted(_all_report_posts, key=lambda p: getattr(p, 'reply_count', 0), reverse=True)
    debated_unique = [p for p in debated if p.id not in shown_post_ids][:6]
    debated_section = ""
    if debated_unique and any(getattr(p, 'reply_count', 0) > 0 for p in debated_unique):
        debated_section = "\n\nMost debated threads (by reply count):\n"
        for post in debated_unique:
            rc = getattr(post, 'reply_count', 0)
            if rc > 0:
                debated_section += f"- [{post.platform}] {post.author_name}: {post.content[:200]} (replies: {rc})\n"

    prompt = (
        f"Domain: {domain}\n"
        f"Product: {idea_text}\n\n"
        + precomputed_block
        + demographics_section
        + f"\nSimulation results across platforms:\n\n"
        + "\n\n".join(platform_summaries)
        + debated_section
        + f"\n\nInstructions:\n"
        f"- verdict: overall market reception\n"
        f"- segments: include all 10 segment types (developer, investor, early_adopter, skeptic, pm, founder, executive, designer, marketer, analyst) even if some have neutral sentiment\n"
        f"- praise_clusters: top 2-4 recurring praise themes\n"
        f"- criticism_clusters: top 3-5 recurring objections\n"
        f"- improvements: top 3-5 actionable suggestions\n"
        f"- key_debates: Identify 2-3 key debates where agents strongly disagreed. For each: topic, main arguments for and against, and how it was resolved (or remains contested). key_debates resolution must reference actual attitude shifts observed in the Attitude shifts section above\n"
        f"- next_steps: 2-5 prioritized actions, grounded in simulation evidence. P0 = must fix before launch, P1 = important but not blocking, P2 = improvements for growth.\n"
        f"- key_quotes MUST be verbatim excerpts (exact wording) from the 'Segment evidence' section above, not paraphrases.\n"
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
            "praise_clusters": [],
            "criticism_clusters": [],
            "improvements": [],
            "key_debates": [],
            "next_steps": [],
        }

    # ── Python-computed fields (not LLM-generated) ──────────────────────────

    # Platform-level sentiment breakdown (including constructive + weighted sentiment)
    PLATFORM_VOTE_WEIGHTS = {
        "hackernews": 1.5,
        "linkedin": 0.8,
        "reddit_startups": 1.0,
        "producthunt": 1.2,
        "indiehackers": 1.0,
    }
    platform_sentiment: dict[str, dict[str, object]] = {}
    all_posts: list = []
    # Accumulators for global weighted sentiment (used for adoption_score)
    global_weighted_positive = 0.0
    global_weighted_neutral = 0.0
    global_weighted_negative = 0.0
    global_weighted_constructive = 0.0
    for state in platform_states:
        posts = state.posts
        all_posts.extend(posts)
        counts: dict[str, int] = {"positive": 0, "neutral": 0, "negative": 0, "constructive": 0}
        weighted: dict[str, float] = {
            "weighted_positive": 0.0,
            "weighted_neutral": 0.0,
            "weighted_negative": 0.0,
            "weighted_constructive": 0.0,
        }
        for post in posts:
            if post.author_node_id == "__seed__":
                continue
            s = getattr(post, "sentiment", "") or ""
            if s in counts:
                counts[s] += 1
            # Weighted sentiment: weight = max(1, upvotes - downvotes) * platform vote weight
            plat_weight = PLATFORM_VOTE_WEIGHTS.get(state.platform_name, 1.0)
            w = max(1, getattr(post, "upvotes", 0) - getattr(post, "downvotes", 0)) * plat_weight
            if s == "positive":
                weighted["weighted_positive"] += w
            elif s == "neutral":
                weighted["weighted_neutral"] += w
            elif s == "negative":
                weighted["weighted_negative"] += w
            elif s == "constructive":
                weighted["weighted_constructive"] += w
        total = sum(counts.values())
        if total > 0:
            pv = (
                "positive" if counts["positive"] > counts["negative"] and counts["positive"] > counts["neutral"]
                else "negative" if counts["negative"] > counts["positive"] and counts["negative"] > counts["neutral"]
                else "mixed"
            )
            platform_sentiment[state.platform_name] = {
                **counts,
                "verdict": pv,
                "total": total,
                "positive_pct": round(counts.get("positive", 0) / max(total, 1) * 100),
                "weighted_positive": weighted["weighted_positive"],
                "weighted_neutral": weighted["weighted_neutral"],
                "weighted_negative": weighted["weighted_negative"],
                "weighted_constructive": weighted["weighted_constructive"],
            }
        global_weighted_positive += weighted["weighted_positive"]
        global_weighted_neutral += weighted["weighted_neutral"]
        global_weighted_negative += weighted["weighted_negative"]
        global_weighted_constructive += weighted["weighted_constructive"]
    report_json["platform_summaries"] = platform_sentiment

    # engagement_quality per platform (Python-computed, no LLM call)
    for state in platform_states:
        plat_posts = [p for p in state.posts if p.author_node_id != "__seed__"]
        if not plat_posts or state.platform_name not in platform_sentiment:
            continue

        # depth_score: average reply_count normalised (5 replies = 1.0)
        avg_reply = sum(p.reply_count or 0 for p in plat_posts) / len(plat_posts)
        depth_score = min(avg_reply / 5.0, 1.0)

        # diversity_score: unique authors normalised (15 unique = 1.0)
        author_ids = {p.author_node_id for p in plat_posts}
        diversity_score = min(len(author_ids) / 15.0, 1.0)

        # constructive_ratio: fraction of posts with constructive sentiment
        constructive = sum(1 for p in plat_posts if p.sentiment == "constructive")
        constructive_ratio = constructive / len(plat_posts)

        # reply_ratio: fraction of posts that are replies/comments/answers
        reply_actions = {"reply", "comment", "answer"}
        reply_ratio = sum(1 for p in plat_posts if p.action_type in reply_actions) / len(plat_posts)

        eq = round(
            (depth_score * 0.25 + diversity_score * 0.25 + constructive_ratio * 0.25 + reply_ratio * 0.25) * 100
        )
        platform_sentiment[state.platform_name]["engagement_quality"] = eq

    # consensus_score: cross-platform agreement on positive sentiment
    pcts = [
        v.get("positive_pct", 0)
        for v in platform_sentiment.values()
        if isinstance(v, dict)
    ]
    if len(pcts) >= 2:
        import statistics
        avg = statistics.mean(pcts)
        stdev = statistics.stdev(pcts) if len(pcts) > 1 else 0
        consensus_score = round(max(0, min(100, avg - stdev)))
    else:
        consensus_score = pcts[0] if pcts else 0
    report_json["consensus_score"] = consensus_score

    # 플랫폼 쌍별 positive_pct 차이 30%p 이상인 경우 divergence 감지
    platform_divergence = []
    psum_items = [
        (k, v) for k, v in report_json.get("platform_summaries", {}).items()
        if isinstance(v, dict) and "positive_pct" in v
    ]
    for i in range(len(psum_items)):
        for j in range(i + 1, len(psum_items)):
            pa, va = psum_items[i]
            pb, vb = psum_items[j]
            gap = abs(va["positive_pct"] - vb["positive_pct"])
            if gap >= 30:
                direction = f"{pa} more positive" if va["positive_pct"] > vb["positive_pct"] else f"{pb} more positive"
                platform_divergence.append({
                    "platform_a": pa,
                    "platform_b": pb,
                    "gap_pct": gap,
                    "direction": direction,
                })
    report_json["platform_divergence"] = platform_divergence

    # agent_participation_rate: fraction of agents who actually posted (excluding seed)
    if total_agent_count > 0:
        unique_authors = len(set(
            p.author_node_id for state in platform_states
            for p in state.posts
            if p.author_node_id != "__seed__"
        ))
        agent_participation_rate = round(unique_authors / max(total_agent_count, 1), 3)
        report_json["agent_participation_rate"] = agent_participation_rate

    # adoption_score: upvote-weighted sentiment score (0-100)
    # constructive is treated as close to neutral (weight 0.5 between positive and neutral)
    total_weighted = (
        global_weighted_positive
        + global_weighted_neutral
        + global_weighted_negative
        + global_weighted_constructive
    )
    adoption_raw = int(
        (
            global_weighted_positive * 100
            + global_weighted_neutral * 40
            + global_weighted_constructive * 50  # constructive ~ neutral-ish (0.5 weight)
        )
        / max(1, total_weighted)
    )
    report_json["adoption_score"] = max(0, min(100, adoption_raw))

    # Round-level sentiment timeline
    timeline_data: dict[int, dict[str, int]] = {}
    for post in all_posts:
        if post.author_node_id == "__seed__":
            continue
        rn = getattr(post, "round_num", 0)
        s = getattr(post, "sentiment", "") or "neutral"
        if rn not in timeline_data:
            timeline_data[rn] = {"positive": 0, "neutral": 0, "negative": 0, "constructive": 0}
        if s in timeline_data[rn]:
            timeline_data[rn][s] += 1
    # Compute vote activity per round from vote_rounds
    vote_activity_by_round: dict[int, int] = {}
    for post in all_posts:
        for vr in getattr(post, "vote_rounds", []):
            vote_activity_by_round[vr] = vote_activity_by_round.get(vr, 0) + 1
    sentiment_timeline = [
        {"round": rn, **counts, "engagement": sum(counts.values()) + vote_activity_by_round.get(rn, 0)}
        for rn, counts in sorted(timeline_data.items())
        if rn > 0
    ]
    # Inject segment_distribution into each timeline entry
    if round_segment_distributions:
        for entry in sentiment_timeline:
            entry["segment_distribution"] = round_segment_distributions.get(entry["round"], {})
    if round_action_type_distributions:
        for entry in sentiment_timeline:
            entry["action_type_distribution"] = round_action_type_distributions.get(entry["round"], {})
    if round_pass_counts:
        for entry in sentiment_timeline:
            round_num = entry.get("round", 0)
            entry["pass_count"] = round_pass_counts.get(round_num, 0)
    if round_inactive_counts:
        for entry in sentiment_timeline:
            round_num = entry.get("round", 0)
            entry["inactive_count"] = round_inactive_counts.get(round_num, 0)
    report_json["sentiment_timeline"] = sentiment_timeline

    # ── Engagement alerts: detect rounds with >= 40% engagement drop ──────
    engagement_alerts = []
    timeline = report_json.get("sentiment_timeline", [])
    for i in range(1, len(timeline)):
        prev_eng = timeline[i-1].get("engagement", 0)
        curr_eng = timeline[i].get("engagement", 0)
        if prev_eng > 0:
            drop_pct = round((prev_eng - curr_eng) / prev_eng * 100)
            if drop_pct >= 40:  # 40% 이상 하락 시 경고
                engagement_alerts.append({
                    "round": timeline[i].get("round"),
                    "drop_pct": drop_pct,
                    "prev_engagement": prev_eng,
                    "curr_engagement": curr_eng,
                })
    report_json["engagement_alerts"] = engagement_alerts

    # ── Max conversation depth per round (Item 6) ─────────────────────────
    all_posts_by_id: dict[str, SocialPost] = {}
    for state in platform_states:
        for post in state.posts:
            all_posts_by_id[post.id] = post

    _depth_memo: dict[str, int] = {}

    def _get_depth(post_id: str) -> int:
        if post_id not in all_posts_by_id:
            return 0
        if post_id in _depth_memo:
            return _depth_memo[post_id]
        post_obj = all_posts_by_id[post_id]
        if not post_obj.parent_id:
            _depth_memo[post_id] = 1
            return 1
        # sentinel: 순환참조 방어 — 재귀 진입 전 0을 삽입하여 순환 시 0 반환
        _depth_memo[post_id] = 0
        _depth_memo[post_id] = 1 + _get_depth(post_obj.parent_id)
        return _depth_memo[post_id]

    max_depth_by_round: dict[int, int] = {}
    for state in platform_states:
        for post in state.posts:
            rn = getattr(post, 'round_num', 0)
            depth = _get_depth(post.id)
            if rn not in max_depth_by_round or depth > max_depth_by_round[rn]:
                max_depth_by_round[rn] = depth

    # merge max_depth into sentiment_timeline
    for entry in report_json.get("sentiment_timeline", []):
        rn = entry.get("round")
        if rn is not None:
            entry["max_depth"] = max_depth_by_round.get(rn, 1)

    # Platform-level sentiment timeline
    plat_timeline_data: dict[str, dict[int, dict[str, int]]] = {}
    for post in all_posts:
        if post.author_node_id == "__seed__":
            continue
        plat = getattr(post, "platform", "") or ""
        rn = getattr(post, "round_num", 0)
        if rn <= 0 or not plat:
            continue
        s = getattr(post, "sentiment", "") or "neutral"
        if plat not in plat_timeline_data:
            plat_timeline_data[plat] = {}
        if rn not in plat_timeline_data[plat]:
            plat_timeline_data[plat][rn] = {"positive": 0, "neutral": 0, "negative": 0, "constructive": 0}
        if s in plat_timeline_data[plat][rn]:
            plat_timeline_data[plat][rn][s] += 1
    platform_sentiment_timeline: dict[str, list[dict]] = {}
    for plat, rounds in sorted(plat_timeline_data.items()):
        platform_sentiment_timeline[plat] = [
            {"round": rn, **counts}
            for rn, counts in sorted(rounds.items())
        ]
    report_json["platform_sentiment_timeline"] = platform_sentiment_timeline

    persona_map_seg = personas or {}
    platform_segments: dict[str, dict[str, dict[str, int]]] = {}
    for post in all_posts:
        plat = getattr(post, "platform", "") or ""
        if not plat:
            continue
        author_id = getattr(post, "author_node_id", "") or ""
        if author_id == "__seed__":
            continue
        persona_obj = persona_map_seg.get(author_id)
        segment = _classify_segment(persona_obj) if persona_obj else "other"
        s = getattr(post, "sentiment", "") or "neutral"
        if s not in ("positive", "neutral", "negative", "constructive"):
            s = "neutral"
        if plat not in platform_segments:
            platform_segments[plat] = {}
        if segment not in platform_segments[plat]:
            platform_segments[plat][segment] = {"positive": 0, "neutral": 0, "negative": 0, "constructive": 0, "total": 0}
        platform_segments[plat][segment][s] += 1
        platform_segments[plat][segment]["total"] += 1
    # positive_pct / negative_pct 추가
    for _plat_segs in platform_segments.values():
        for seg, counts in _plat_segs.items():
            total = counts.get("total", 1) or 1
            counts["positive_pct"] = round(counts.get("positive", 0) / total * 100)
            counts["negative_pct"] = round(counts.get("negative", 0) / total * 100)
            counts["constructive_pct"] = round(counts.get("constructive", 0) / total * 100)
            counts["effective_positive_pct"] = round((counts.get("positive", 0) + counts.get("constructive", 0) * 0.5) / total * 100)
    report_json["platform_segments"] = platform_segments

    # ── Segment sentiment Python-based correction ───────────────────────────
    # Override LLM-generated segment sentiment with Python-computed values
    if "segments" in report_json and platform_segments:
        seg_totals: dict[str, dict] = {}
        for plat_segs in platform_segments.values():
            for seg_name, seg_data in plat_segs.items():
                if seg_name not in seg_totals:
                    seg_totals[seg_name] = {"positive": 0, "neutral": 0, "negative": 0, "total": 0}
                seg_totals[seg_name]["positive"] += seg_data.get("positive", 0)
                seg_totals[seg_name]["neutral"] += seg_data.get("neutral", 0) + seg_data.get("constructive", 0)
                seg_totals[seg_name]["negative"] += seg_data.get("negative", 0)
                seg_totals[seg_name]["total"] += seg_data.get("total", 0)

        for seg in report_json["segments"]:
            seg_name = seg.get("name", "")
            if seg_name in seg_totals:
                tot = seg_totals[seg_name]
                total = tot["total"] or 1
                pos_pct = tot["positive"] / total
                neg_pct = tot["negative"] / total
                if pos_pct > 0.5:
                    seg["sentiment"] = "positive"
                elif neg_pct > 0.4:
                    seg["sentiment"] = "negative"
                else:
                    seg["sentiment"] = "neutral"
                seg["sentiment_ratio"] = f"{int(pos_pct*100)}% positive, {int(tot['neutral']/total*100)}% neutral, {int(neg_pct*100)}% negative"

    # ── Interaction network from replies (Item 7) ───────────────────────────
    reply_pairs: dict[tuple[str, str], dict] = {}
    for state in platform_states:
        for post in state.posts:
            if post.parent_id and post.author_node_id != "__seed__":
                parent = all_posts_by_id.get(post.parent_id)
                if parent and parent.author_node_id != post.author_node_id:
                    key = (post.author_node_id, parent.author_node_id)
                    if key not in reply_pairs:
                        reply_pairs[key] = {"count": 0, "agree_count": 0, "disagree_count": 0}
                    reply_pairs[key]["count"] += 1
                    # agree if same sentiment polarity
                    child_sent = getattr(post, 'sentiment', 'neutral')
                    parent_sent = getattr(parent, 'sentiment', 'neutral')
                    if child_sent == parent_sent:
                        reply_pairs[key]["agree_count"] += 1
                    else:
                        reply_pairs[key]["disagree_count"] += 1

    sorted_pairs = sorted(reply_pairs.items(), key=lambda x: x[1]["count"], reverse=True)[:10]

    def _get_name(nid: str, personas_dict: dict) -> str:
        p = personas_dict.get(nid)
        return p.name if p else nid

    persona_map_net = personas or {}
    report_json["interaction_network"] = [
        {
            "from": k[0],
            "to": k[1],
            "from_name": _get_name(k[0], persona_map_net),
            "to_name": _get_name(k[1], persona_map_net),
            **v,
        }
        for k, v in sorted_pairs
    ]

    # ── Attitude shifts: top-5 personas with largest cumulative change (Item 2) ──
    if personas:
        attitude_data = []
        for nid, p in personas.items():
            history = getattr(p, "attitude_history", [])
            if not history:
                continue
            total_delta = sum(h.get("delta", 0.0) for h in history)
            # Enrich history items with trigger_summary
            enriched_history = []
            for h in history:
                trigger_post = all_posts_by_id.get(h.get("trigger_post_id", ""))
                trigger_summary = trigger_post.content[:100] if trigger_post else ""
                enriched_history.append({**h, "trigger_summary": trigger_summary})
            attitude_data.append({
                "name": p.name,
                "node_id": nid,
                "total_delta": round(total_delta, 3),
                "history": enriched_history,
            })
        attitude_data.sort(key=lambda x: -abs(x["total_delta"]))
        report_json["attitude_shifts"] = attitude_data[:5]

    # ── Influence flow: who actually changed whose attitude ─────────────────
    if personas:
        influence_flow = []
        for nid, p_influenced in personas.items():
            history = getattr(p_influenced, "attitude_history", [])
            for h in history:
                tid = h.get("trigger_post_id", "")
                if not tid or tid == "__cross_sync__":
                    continue
                trigger_post = all_posts_by_id.get(tid)
                if not trigger_post or trigger_post.author_node_id == nid:
                    continue
                p_influencer = personas.get(trigger_post.author_node_id)
                if not p_influencer:
                    continue
                influence_flow.append({
                    "influencer_name": p_influencer.name,
                    "influenced_name": p_influenced.name,
                    "round": h.get("round", 0),
                    "delta": round(h.get("delta", 0.0), 3),
                    "trigger_snippet": trigger_post.content[:120],
                    "influencer_segment": _classify_segment(p_influencer),
                    "influenced_segment": _classify_segment(p_influenced),
                })
        influence_flow.sort(key=lambda x: -abs(x["delta"]))
        report_json["influence_flow"] = influence_flow[:15]

    # ── Segment attitude shifts ──────────────────────────────────────────────
    if personas:
        seg_shifts: dict[str, list[float]] = {}
        for nid, persona_obj in personas.items():
            seg = _classify_segment(persona_obj)
            shift = getattr(persona_obj, 'attitude_shift', 0.0)
            if seg not in seg_shifts:
                seg_shifts[seg] = []
            seg_shifts[seg].append(shift)

        segment_attitude_shifts = []
        for seg, shifts in sorted(seg_shifts.items()):
            if not shifts:
                continue
            avg_delta = round(sum(shifts) / len(shifts), 3)
            shifted = sum(1 for s in shifts if abs(s) > 0.05)
            segment_attitude_shifts.append({
                "segment": seg,
                "avg_delta": avg_delta,
                "count": len(shifts),
                "shifted_count": shifted,
            })
        segment_attitude_shifts.sort(key=lambda x: abs(x["avg_delta"]), reverse=True)
        for item in segment_attitude_shifts:
            count = item.get("count", 0)
            if count < 5:
                item["confidence"] = "low"
            elif count < 15:
                item["confidence"] = "medium"
            else:
                item["confidence"] = "high"
        report_json["segment_attitude_shifts"] = segment_attitude_shifts

    # ── Segment conversion funnel ────────────────────────────────────────────
    if personas:
        seg_funnel: dict[str, dict] = {}
        for nid, p in personas.items():
            seg = _classify_segment(p)
            if seg not in seg_funnel:
                seg_funnel[seg] = {
                    "converted_positive": 0,
                    "converted_negative": 0,
                    "stayed_neutral": 0,
                    "total": 0,
                    "conversion_rate": 0.0,
                    "resistance_rate": 0.0,
                    "_rounds_to_convert": [],
                }
            entry = seg_funnel[seg]
            entry["total"] += 1
            shift = getattr(p, "attitude_shift", 0.0) or 0.0
            if shift >= 0.15:
                entry["converted_positive"] += 1
                history = getattr(p, "attitude_history", []) or []
                first_positive_round = next(
                    (h.get("round", 0) for h in history if h.get("delta", 0) > 0),
                    None,
                )
                if first_positive_round is not None:
                    # 첫 활동 라운드 기준으로 "걸린 라운드 수" 계산 (라운드 번호가 아닌 소요 라운드)
                    first_active_round = history[0].get("round", 0) if history else first_positive_round
                    rounds_taken = max(0, first_positive_round - first_active_round)
                    entry["_rounds_to_convert"].append(rounds_taken)
            elif shift <= -0.15:
                entry["converted_negative"] += 1
            else:
                entry["stayed_neutral"] += 1

        funnel_result = {}
        for seg, entry in seg_funnel.items():
            total = max(entry["total"], 1)
            rnd_list = entry.pop("_rounds_to_convert", [])
            funnel_result[seg] = {
                **entry,
                "conversion_rate": round(entry["converted_positive"] / total * 100, 1),
                "resistance_rate": round(entry["converted_negative"] / total * 100, 1),
                "avg_rounds_to_convert": round(sum(rnd_list) / len(rnd_list), 1) if rnd_list else None,
            }
        report_json["segment_conversion_funnel"] = funnel_result

    # ── Region sentiment 집계 ─────────────────────────────────────────────────
    region_sentiment: dict[str, dict] = {}
    all_posts_flat = [
        p for state in platform_states for p in state.posts
        if p.author_node_id != "__seed__" and not p.id.startswith("__seed__")
    ]
    all_personas_map: dict[str, Persona] = {}
    if personas:
        all_personas_map = dict(personas)

    # ── Segment journey: round-by-round segment sentiment tracking ───────────
    segment_journey: dict[int, dict[str, dict[str, int]]] = {}
    for post in all_posts_flat:
        if str(getattr(post, "id", "")).startswith("__seed__"):
            continue
        r = int(getattr(post, "round_num", 0))
        if r <= 0:
            continue
        persona_sj = all_personas_map.get(getattr(post, "author_node_id", ""))
        if persona_sj is None:
            continue
        seg = _classify_segment(persona_sj)
        sent = getattr(post, "sentiment", "neutral") or "neutral"
        if sent not in ("positive", "negative", "neutral", "constructive"):
            sent = "neutral"
        if r not in segment_journey:
            segment_journey[r] = {}
        if seg not in segment_journey[r]:
            segment_journey[r][seg] = {"positive": 0, "negative": 0, "neutral": 0, "constructive": 0}
        segment_journey[r][seg][sent] += 1
    report_json["segment_journey"] = segment_journey

    # ── Archetype narratives: 세그먼트별 시간축 여정 서사 ─────────────────────
    archetype_narratives: list[dict] = []
    if report_json.get("segment_journey") and report_json.get("segment_attitude_shifts"):
        seg_journey = report_json["segment_journey"]  # dict[int, dict[str, dict[str, int]]]

        for seg_stat in report_json["segment_attitude_shifts"]:
            segment = seg_stat["segment"]

            # 1. 이 세그먼트의 라운드별 positive_ratio 계산
            round_sentiments: list[tuple[int, float, int]] = []
            for rnd in sorted(seg_journey.keys()):
                seg_data = seg_journey[rnd]
                if segment not in seg_data:
                    continue
                counts = seg_data[segment]
                total = sum(counts.values())
                if total == 0:
                    continue
                pos_ratio = counts.get("positive", 0) / total
                round_sentiments.append((rnd, pos_ratio, total))

            if len(round_sentiments) < 2:
                continue

            # 2. pivot round 탐지: positive_ratio가 전 라운드 대비 20%p 이상 변동
            pivot_rounds: list[dict] = []
            for i in range(1, len(round_sentiments)):
                _prev_rnd, prev_ratio, _ = round_sentiments[i - 1]
                curr_rnd, curr_ratio, _ = round_sentiments[i]
                delta = curr_ratio - prev_ratio
                if abs(delta) >= 0.20:
                    direction = "positive" if delta > 0 else "negative"
                    trigger_snippet = ""
                    trigger_author = ""
                    for p in all_posts_flat:
                        p_persona = all_personas_map.get(getattr(p, "author_node_id", ""))
                        if p_persona and _classify_segment(p_persona) == segment and getattr(p, "round_num", 0) == curr_rnd:
                            if not trigger_snippet or (getattr(p, "upvotes", 0) or 0) > 0:
                                trigger_snippet = (getattr(p, "content", "") or "")[:100]
                                trigger_author = getattr(p, "author_name", "") or ""
                                break
                    pivot_rounds.append({
                        "round": curr_rnd,
                        "direction": direction,
                        "delta_pct": round(abs(delta) * 100),
                        "trigger_post_snippet": trigger_snippet,
                        "trigger_author": trigger_author,
                    })

            # 3. journey_summary 문자열 생성 (구간별 dominant sentiment 연결)
            summary_parts: list[str] = []
            block_size = max(1, len(round_sentiments) // 3)
            for block_start in range(0, len(round_sentiments), block_size):
                block = round_sentiments[block_start:block_start + block_size]
                if not block:
                    continue
                avg_pos = sum(r[1] for r in block) / len(block)
                rnd_from = block[0][0]
                rnd_to = block[-1][0]
                label = "positive" if avg_pos >= 0.5 else "mixed" if avg_pos >= 0.35 else "skeptical"
                summary_parts.append(f"R{rnd_from}-R{rnd_to}: {label}")

            archetype_narratives.append({
                "segment": segment,
                "journey_summary": " → ".join(summary_parts),
                "pivot_rounds": pivot_rounds,
                "attitude_delta": seg_stat.get("avg_delta", 0),
                "persona_count": seg_stat.get("count", 0),
            })

        archetype_narratives.sort(key=lambda x: len(x["pivot_rounds"]), reverse=True)

    report_json["archetype_narratives"] = archetype_narratives

    for post in all_posts_flat:
        persona_obj_rs = all_personas_map.get(post.author_node_id)
        if not persona_obj_rs:
            continue
        region = getattr(persona_obj_rs, 'region', None) or "Global"
        if region not in region_sentiment:
            region_sentiment[region] = {"positive": 0, "neutral": 0, "negative": 0, "constructive": 0, "total": 0}
        sentiment = getattr(post, 'sentiment', '') or 'neutral'
        if sentiment in region_sentiment[region]:
            region_sentiment[region][sentiment] += 1
        region_sentiment[region]["total"] += 1

    for region, counts in region_sentiment.items():
        total = max(counts["total"], 1)
        counts["positive_pct"] = round(counts["positive"] / total * 100)
        counts["negative_pct"] = round(counts["negative"] / total * 100)

    report_json["region_sentiment"] = region_sentiment

    # ── Q&A pairs extraction ─────────────────────────────────────────────────
    QUESTION_ACTIONS = {"ask_hn", "ask_question", "ask_advice", "question", "ask"}
    qa_pairs = []
    persona_map_qa = personas or {}
    for state in platform_states:
        for post in state.posts:
            if post.action_type not in QUESTION_ACTIONS:
                continue
            if post.author_node_id == "__seed__":
                continue
            answers = sorted(
                [p for p in state.posts if p.parent_id == post.id],
                key=lambda p: p.upvotes, reverse=True,
            )[:3]  # 최대 3개 답변
            q_author = persona_map_qa.get(post.author_node_id)
            qa_pairs.append({
                "question_id": post.id,
                "question_text": post.content[:200],
                "platform": state.platform_name,
                "author_name": q_author.name if q_author else post.author_name,
                "answers": [
                    {
                        "text": a.content[:150],
                        "author_name": (persona_map_qa.get(a.author_node_id).name if persona_map_qa.get(a.author_node_id) else a.author_name),
                        "upvotes": a.upvotes,
                    }
                    for a in answers
                ],
                "answered": len(answers) > 0,
            })
    # upvotes 합산 기준 내림차순 정렬, 상위 15개
    qa_pairs = sorted(qa_pairs, key=lambda x: sum(a["upvotes"] for a in x["answers"]), reverse=True)[:15]
    report_json["qa_pairs"] = qa_pairs
    # Q&A response_rate (qa_response_rate): 질문 중 답변 받은 비율
    answered_count = sum(1 for q in qa_pairs if q["answered"])
    report_json["qa_response_rate"] = round(answered_count / len(qa_pairs), 3) if qa_pairs else 0.0

    # response_rate: seed 포스트를 제외한 top-level 포스트 중 reply가 1개 이상 달린 비율
    _non_seed_toplevel = [
        p for state in platform_states for p in state.posts
        if p.parent_id is None and p.author_node_id != "__seed__"
    ]
    _replied_toplevel = [p for p in _non_seed_toplevel if (getattr(p, "reply_count", 0) or 0) >= 1]
    report_json["response_rate"] = round(len(_replied_toplevel) / max(len(_non_seed_toplevel), 1), 3)

    # ── Unaddressed concerns: negative/constructive top-level posts with no replies ──
    _replied_parent_ids: set[str] = set()
    for state in platform_states:
        for post in state.posts:
            if post.parent_id:
                _replied_parent_ids.add(post.parent_id)

    unaddressed_candidates = []
    _uc_personas_map = personas or {}
    for state in platform_states:
        for post in state.posts:
            if post.author_node_id == "__seed__":
                continue
            if post.parent_id is not None:
                continue  # not top-level
            _post_sentiment = getattr(post, "sentiment", "") or ""
            if _post_sentiment not in ("negative", "constructive"):
                continue
            if post.id in _replied_parent_ids:
                continue
            if getattr(post, "reply_count", 0) > 0:
                continue
            persona_obj_uc = _uc_personas_map.get(post.author_node_id)
            author_seg = _classify_segment(persona_obj_uc) if persona_obj_uc else "unknown"
            unaddressed_candidates.append({
                "post_id": post.id,
                "platform": post.platform,
                "author_name": post.author_name,
                "author_segment": author_seg,
                "content_snippet": post.content[:120],
                "sentiment": _post_sentiment,
                "weighted_score": getattr(post, "weighted_score", 0.0),
            })
    # Sort by weighted_score descending, take top 5
    unaddressed_candidates.sort(key=lambda x: x["weighted_score"], reverse=True)
    report_json["unaddressed_concerns"] = unaddressed_candidates[:5]

    # ── Top contributors (Item 5) ─────────────────────────────────────────
    contributor_scores: dict[str, dict] = {}
    for state in platform_states:
        for post in state.posts:
            nid = post.author_node_id
            if nid == "__seed__":
                continue
            if nid not in contributor_scores:
                contributor_scores[nid] = {"posts": 0, "post_score": 0, "replies_received": 0, "upvotes": 0, "mentions": 0}
            contributor_scores[nid]["posts"] += 1
            # sentiment에 따라 가중 점수
            sentiment = getattr(post, 'sentiment', 'neutral')
            post_score = {"positive": 3, "constructive": 3, "neutral": 2, "negative": 1}.get(sentiment, 2)
            contributor_scores[nid]["post_score"] = contributor_scores[nid].get("post_score", 0) + post_score
            contributor_scores[nid]["upvotes"] += post.upvotes
            # mentions received
            mentions = post.structured_data.get("mentions", []) if post.structured_data else []
            if mentions:
                _name_to_nid = {p.name.lower(): nid_ for nid_, p in (personas or {}).items()}
                for m in mentions:
                    target_nid = _name_to_nid.get(m.lower())
                    if target_nid and target_nid in contributor_scores:
                        contributor_scores[target_nid]["mentions"] += 1

    # count replies_received
    for state in platform_states:
        for post in state.posts:
            if post.parent_id and post.author_node_id != "__seed__":
                parent = all_posts_by_id.get(post.parent_id)
                if parent and parent.author_node_id in contributor_scores:
                    contributor_scores[parent.author_node_id]["replies_received"] += 1

    top_contributors = []
    persona_map_tc = personas or {}
    for nid, s in contributor_scores.items():
        score = s.get("post_score", s["posts"] * 2) + s["replies_received"] * 2 + s["upvotes"] * 1 + s["mentions"] * 2
        persona_obj_tc = persona_map_tc.get(nid)
        name = persona_obj_tc.name if persona_obj_tc else nid
        top_contributors.append({"name": name, "node_id": nid, "score": score, **s})

    top_contributors.sort(key=lambda x: x["score"], reverse=True)

    # influence_score: influence_flow에서 influencer로 등장한 delta 절대값 합산
    _influencer_score_map: dict[str, float] = {}
    for _flow in report_json.get("influence_flow", []):
        _inf_name = _flow.get("influencer_name", "")
        _influencer_score_map[_inf_name] = _influencer_score_map.get(_inf_name, 0.0) + abs(_flow.get("delta", 0.0))
    for contrib in top_contributors:
        contrib["influence_score"] = round(_influencer_score_map.get(contrib.get("name", ""), 0.0), 3)

    report_json["top_contributors"] = top_contributors[:5]

    # ── Item 1: convergence_round 필드 추가 ──────────────────────────────────
    report_json["convergence_round"] = convergence_round

    # ── Item 4: 리포트 자동 검증 ─────────────────────────────────────────────
    _validate_report(
        report_json,
        total_posts=total_evidence,
        adoption_score=report_json.get("adoption_score", 50),
    )

    report_md = _render_report_md(report_json, idea_text, language)
    return report_json, report_md


_REPORT_I18N: dict[str, dict[str, str]] = {
    "Korean": {
        "overall_verdict": "종합 평가",
        "based_on": "{n}개의 시뮬레이션 인터랙션 기반",
        "segment_reactions": "세그먼트별 반응",
        "praise_patterns": "공감 포인트",
        "criticism_patterns": "비판 패턴",
        "improvement_suggestions": "개선 제안",
        "mentions": "{n}회 언급",
        "seg_developer": "개발자",
        "seg_investor": "투자자",
        "seg_early_adopter": "얼리 어답터",
        "seg_skeptic": "회의론자",
        "seg_pm": "프로덕트 매니저",
        "seg_founder": "창업자",
        "seg_executive": "임원",
        "seg_designer": "디자이너",
        "seg_marketer": "마케터",
        "seg_analyst": "분석가",
        "verdict_positive": "긍정적",
        "verdict_mixed": "복합적",
        "verdict_skeptical": "회의적",
        "verdict_negative": "부정적",
        "platform_reception": "플랫폼별 반응",
        "key_debates": "핵심 논쟁",
        "attitude_shifts": "태도 변화",
        "recommended_actions": "권장 액션",
        "unaddressed_concerns": "미응답 우려사항",
    },
    "Japanese": {
        "overall_verdict": "総合評価",
        "based_on": "{n}件のシミュレーションインタラクションに基づく",
        "segment_reactions": "セグメント別反応",
        "praise_patterns": "評価されたポイント",
        "criticism_patterns": "批判パターン",
        "improvement_suggestions": "改善提案",
        "mentions": "{n}回言及",
        "seg_developer": "開発者",
        "seg_investor": "投資家",
        "seg_early_adopter": "アーリーアダプター",
        "seg_skeptic": "懐疑論者",
        "seg_pm": "プロダクトマネージャー",
        "seg_founder": "創業者",
        "seg_executive": "エグゼクティブ",
        "seg_designer": "デザイナー",
        "seg_marketer": "マーケター",
        "seg_analyst": "アナリスト",
        "verdict_positive": "肯定的",
        "verdict_mixed": "混合",
        "verdict_skeptical": "懐疑的",
        "verdict_negative": "否定的",
        "platform_reception": "プラットフォーム別反応",
        "key_debates": "主要な議論",
        "attitude_shifts": "態度の変化",
        "recommended_actions": "推奨アクション",
        "unaddressed_concerns": "未対応の懸念事項",
    },
    "Chinese": {
        "overall_verdict": "综合评估",
        "based_on": "基于{n}次模拟互动",
        "segment_reactions": "细分市场反应",
        "praise_patterns": "共鸣点",
        "criticism_patterns": "批评模式",
        "improvement_suggestions": "改进建议",
        "mentions": "提及{n}次",
        "seg_developer": "开发者",
        "seg_investor": "投资者",
        "seg_early_adopter": "早期采用者",
        "seg_skeptic": "怀疑者",
        "seg_pm": "产品经理",
        "seg_founder": "创始人",
        "seg_executive": "高管",
        "seg_designer": "设计师",
        "seg_marketer": "营销人员",
        "seg_analyst": "分析师",
        "verdict_positive": "积极",
        "verdict_mixed": "复杂",
        "verdict_skeptical": "怀疑",
        "verdict_negative": "消极",
        "platform_reception": "平台反应",
        "key_debates": "关键争论",
        "attitude_shifts": "态度变化",
        "recommended_actions": "建议行动",
        "unaddressed_concerns": "未回应的关切",
    },
    "Spanish": {
        "overall_verdict": "Veredicto General",
        "based_on": "Basado en {n} interacciones simuladas",
        "segment_reactions": "Reacciones por Segmento",
        "praise_patterns": "Lo que resonó",
        "criticism_patterns": "Patrones de Crítica",
        "improvement_suggestions": "Sugerencias de Mejora",
        "mentions": "mencionado {n} veces",
        "seg_developer": "Desarrollador",
        "seg_investor": "Inversor",
        "seg_early_adopter": "Adoptante Temprano",
        "seg_skeptic": "Escéptico",
        "seg_pm": "Product Manager",
        "seg_founder": "Founders",
        "seg_executive": "Executives",
        "seg_designer": "Designers",
        "seg_marketer": "Marketers",
        "seg_analyst": "Analista",
        "verdict_positive": "Positivo",
        "verdict_mixed": "Mixto",
        "verdict_skeptical": "Escéptico",
        "verdict_negative": "Negativo",
        "platform_reception": "Recepción por plataforma",
        "key_debates": "Debates Clave",
        "attitude_shifts": "Cambios de actitud",
        "recommended_actions": "Acciones Recomendadas",
        "unaddressed_concerns": "Preocupaciones sin respuesta",
    },
    "French": {
        "overall_verdict": "Verdict Global",
        "based_on": "Basé sur {n} interactions simulées",
        "segment_reactions": "Réactions par Segment",
        "praise_patterns": "Ce qui a résonné",
        "criticism_patterns": "Patterns de Critique",
        "improvement_suggestions": "Suggestions d'Amélioration",
        "mentions": "mentionné {n} fois",
        "seg_developer": "Développeur",
        "seg_investor": "Investisseur",
        "seg_early_adopter": "Adopteur Précoce",
        "seg_skeptic": "Sceptique",
        "seg_pm": "Product Manager",
        "seg_founder": "Founders",
        "seg_executive": "Executives",
        "seg_designer": "Designers",
        "seg_marketer": "Marketers",
        "seg_analyst": "Analyste",
        "verdict_positive": "Positif",
        "verdict_mixed": "Mixte",
        "verdict_skeptical": "Sceptique",
        "verdict_negative": "Négatif",
        "platform_reception": "Réception par plateforme",
        "key_debates": "Débats Clés",
        "attitude_shifts": "Évolutions d'attitude",
        "recommended_actions": "Actions Recommandées",
        "unaddressed_concerns": "Préoccupations sans réponse",
    },
    "German": {
        "overall_verdict": "Gesamtbewertung",
        "based_on": "Basierend auf {n} simulierten Interaktionen",
        "segment_reactions": "Segmentreaktionen",
        "praise_patterns": "Was Anklang fand",
        "criticism_patterns": "Kritikuster",
        "improvement_suggestions": "Verbesserungsvorschläge",
        "mentions": "{n}x erwähnt",
        "seg_developer": "Entwickler",
        "seg_investor": "Investor",
        "seg_early_adopter": "Early Adopter",
        "seg_skeptic": "Skeptiker",
        "seg_pm": "Produktmanager",
        "seg_founder": "Founders",
        "seg_executive": "Executives",
        "seg_designer": "Designers",
        "seg_marketer": "Marketers",
        "seg_analyst": "Analyst",
        "verdict_positive": "Positiv",
        "verdict_mixed": "Gemischt",
        "verdict_skeptical": "Skeptisch",
        "verdict_negative": "Negativ",
        "platform_reception": "Plattform-Reaktionen",
        "key_debates": "Zentrale Debatten",
        "attitude_shifts": "Einstellungsänderungen",
        "recommended_actions": "Empfohlene Maßnahmen",
        "unaddressed_concerns": "Unbehandelte Bedenken",
    },
    "Portuguese": {
        "overall_verdict": "Veredicto Geral",
        "based_on": "Baseado em {n} interações simuladas",
        "segment_reactions": "Reações por Segmento",
        "praise_patterns": "O que ressoou",
        "criticism_patterns": "Padrões de Crítica",
        "improvement_suggestions": "Sugestões de Melhoria",
        "mentions": "mencionado {n} vezes",
        "seg_developer": "Desenvolvedor",
        "seg_investor": "Investidor",
        "seg_early_adopter": "Adotante Inicial",
        "seg_skeptic": "Cético",
        "seg_pm": "Gerente de Produto",
        "seg_founder": "Founders",
        "seg_executive": "Executives",
        "seg_designer": "Designers",
        "seg_marketer": "Marketers",
        "seg_analyst": "Analista",
        "verdict_positive": "Positivo",
        "verdict_mixed": "Misto",
        "verdict_skeptical": "Cético",
        "verdict_negative": "Negativo",
        "platform_reception": "Recepção por plataforma",
        "key_debates": "Debates Principais",
        "attitude_shifts": "Mudanças de atitude",
        "recommended_actions": "Ações Recomendadas",
        "unaddressed_concerns": "Preocupações sem resposta",
    },
    "English": {
        "overall_verdict": "Overall Verdict",
        "based_on": "Based on {n} simulated interactions",
        "segment_reactions": "Segment Reactions",
        "praise_patterns": "What Resonated",
        "criticism_patterns": "Criticism Patterns",
        "improvement_suggestions": "Improvement Suggestions",
        "mentions": "mentioned {n}x",
        "seg_developer": "Developer",
        "seg_investor": "Investor",
        "seg_early_adopter": "Early Adopter",
        "seg_skeptic": "Skeptic",
        "seg_pm": "Product Manager",
        "seg_founder": "Founders",
        "seg_executive": "Executives",
        "seg_designer": "Designers",
        "seg_marketer": "Marketers",
        "seg_analyst": "Analyst",
        "verdict_positive": "Positive",
        "verdict_mixed": "Mixed",
        "verdict_skeptical": "Skeptical",
        "verdict_negative": "Negative",
        "platform_reception": "Platform Reception",
        "key_debates": "Key Debates",
        "attitude_shifts": "Attitude Shifts",
        "recommended_actions": "Recommended Actions",
        "unaddressed_concerns": "Unaddressed Concerns",
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
        "founder": t.get("seg_founder", "Founders"),
        "executive": t.get("seg_executive", "Executives"),
        "designer": t.get("seg_designer", "Designers"),
        "marketer": t.get("seg_marketer", "Marketers"),
        "analyst": t.get("seg_analyst", "Analyst"),
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

    praise_clusters = report.get("praise_clusters", [])
    if praise_clusters:
        lines += [f"## {t['praise_patterns']}"]
        for cluster in praise_clusters:
            n = cluster.get("count", 0)
            lines.append(f"### {cluster.get('theme', '')} ({t['mentions'].format(n=n)})")
            for ex in cluster.get("examples", [])[:2]:
                ex = ex.strip().strip('"\u201c\u201d')
                lines.append(f'- "{ex}"')
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

    # Key Debates section
    key_debates = report.get("key_debates")
    if key_debates:
        lines.append("")
        lines.append(f"## {t['key_debates']}")
        for debate in key_debates:
            lines.append(f"### {debate.get('topic', '')}")
            for arg in debate.get("for_arguments", []):
                lines.append(f"- **+** {arg}")
            for arg in debate.get("against_arguments", []):
                lines.append(f"- **-** {arg}")
            resolution = debate.get("resolution", "")
            if resolution:
                lines.append(f"  *{resolution}*")
            lines.append("")

    # Recommended Actions (next_steps) section
    next_steps = report.get("next_steps", [])
    if next_steps:
        next_steps_heading = t.get("recommended_actions", "Recommended Actions")
        lines.append("")
        lines.append(f"## {next_steps_heading}")
        lines.append("")
        for step in next_steps:
            priority = step.get("priority", "P1")
            action = step.get("action", "")
            rationale = step.get("rationale", "")
            lines.append(f"**[{priority}]** {action}")
            lines.append(f"> {rationale}")
            segment_impact = step.get("segment_impact", [])
            if segment_impact:
                lines.append(f"> Segments: {', '.join(str(s) for s in segment_impact)}")
            lines.append("")

    # Unaddressed Concerns section
    unaddressed = report.get("unaddressed_concerns", [])
    if unaddressed:
        uc_heading = t.get("unaddressed_concerns", "Unaddressed Concerns")
        lines.append("")
        lines.append(f"## {uc_heading}")
        lines.append("")
        for uc in unaddressed:
            _uc_plat = uc.get("platform", "")
            _uc_author = uc.get("author_name", "")
            _uc_seg = uc.get("author_segment", "")
            _uc_snippet = uc.get("content_snippet", "")
            _uc_ws = uc.get("weighted_score", 0.0)
            lines.append(f"- [{_uc_plat}] **{_uc_author}** ({_uc_seg}): {_uc_snippet}... (weighted_score: {_uc_ws:.1f})")
        lines.append("")

    # attitude_shifts 섹션
    attitude_shifts = report.get("attitude_shifts", [])
    if attitude_shifts:
        heading = t.get("attitude_shifts", "Attitude Shifts")
        lines.append(f"\n## {heading}\n")
        for item in attitude_shifts[:5]:
            delta_str = f"+{item['total_delta']:.2f}" if item['total_delta'] > 0 else f"{item['total_delta']:.2f}"
            lines.append(f"- **{item['name']}**: {delta_str}")
            for h in item.get("history", [])[:2]:
                summary = h.get("trigger_summary", "")
                if summary:
                    lines.append(f"  - Round {h['round']}: *\"{summary}\"*")
        lines.append("")

    # Platform Reception section
    platform_summaries = report.get("platform_summaries")
    if platform_summaries:
        lines.append("")
        lines.append(f"## {t['platform_reception']}")
        for plat_name, stats in platform_summaries.items():
            if not isinstance(stats, dict):
                continue
            pos = stats.get("positive", 0)
            neu = stats.get("neutral", 0)
            neg = stats.get("negative", 0)
            con = stats.get("constructive", 0)
            verdict_val = stats.get("verdict", "")
            verdict_str = f" — {verdict_val}" if verdict_val else ""
            con_str = f" / 🔧{con}" if con else ""
            lines.append(
                f"- **{plat_name}**: +{pos} / ~{neu} / -{neg}{con_str}{verdict_str}"
            )
        lines.append("")

    return "\n".join(lines)
