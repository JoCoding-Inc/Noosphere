from __future__ import annotations
import asyncio
import dataclasses
import logging
import math
from collections import defaultdict, deque
from collections.abc import AsyncGenerator

from backend.simulation.models import Persona, PlatformState, SocialPost
from backend.simulation.graph_utils import build_adjacency, build_clusters
from backend.simulation.social_rounds import (
    round_personas, generate_seed_post, platform_round, generate_report,
    _classify_segment,
)
from backend.simulation.persona_generator import _validate_persona_distribution, load_agent_pool
from backend.simulation.persona_selector import get_distribution, select_agents_for_platform
from backend.simulation.platforms import PLATFORM_MAP
from backend import llm as _llm

logger = logging.getLogger(__name__)

PLATFORM_NAMES = ["hackernews", "producthunt", "indiehackers", "reddit_startups", "linkedin"]

# Seniority-based influence weights for cross-platform attitude contagion
_SENIORITY_WEIGHTS: dict[str, float] = {
    "c_suite": 1.8, "vp": 1.6, "director": 1.5, "principal": 1.4,
    "lead": 1.3, "senior": 1.2, "mid": 1.0, "junior": 0.8, "intern": 0.6,
}


def _compute_echo_chamber_risk(platform_states: list, all_posts_by_platform: dict) -> dict:
    """
    플랫폼별 echo chamber 위험도를 3가지 지표로 측정.

    반환: dict[platform_name, {
        "risk": "low" | "medium" | "high",
        "entropy": float,  # Shannon entropy 0-1 정규화 (기존 프론트엔드 타입과 호환)
        "sentiment_homogeneity": float,
        "opinion_diversity": float,
        "cross_reply_polarity": float,
        "dominant_sentiment": str,
    }]
    """
    result = {}
    for state in platform_states:
        posts = [p for p in state.posts if p.author_node_id != "__seed__"]
        if not posts:
            continue

        platform_name = state.platform_name

        # 지표 1: Sentiment Homogeneity (마지막 3라운드 dominant sentiment 비율)
        max_round = max((p.round_num for p in posts), default=0)
        recent_posts = [p for p in posts if p.round_num >= max_round - 2]
        if recent_posts:
            sent_counts: dict[str, int] = {}
            for p in recent_posts:
                s = p.sentiment or "neutral"
                sent_counts[s] = sent_counts.get(s, 0) + 1
            dominant = max(sent_counts, key=sent_counts.get)
            dominant_ratio = sent_counts[dominant] / len(recent_posts)
        else:
            dominant, dominant_ratio = "neutral", 0.0

        # 지표 2: Opinion Diversity Index (Shannon entropy)
        all_sent: dict[str, int] = {}
        for p in posts:
            s = p.sentiment or "neutral"
            all_sent[s] = all_sent.get(s, 0) + 1
        total = sum(all_sent.values())
        if total > 0 and len(all_sent) > 1:
            entropy = -sum(
                (c / total) * math.log2(c / total) for c in all_sent.values() if c > 0
            )
            max_entropy = math.log2(len(all_sent))
            normalized_entropy = entropy / max_entropy if max_entropy > 0 else 0.0
        else:
            normalized_entropy = 0.0

        # 지표 3: Cross-reply Polarity (reply sentiment == parent sentiment 비율)
        reply_posts = [p for p in posts if p.parent_id]
        if reply_posts:
            posts_by_id = {p.id: p for p in state.posts}
            same_polarity = sum(
                1
                for r in reply_posts
                if (parent := posts_by_id.get(r.parent_id))
                and r.sentiment == parent.sentiment
            )
            cross_reply_polarity = same_polarity / len(reply_posts)
        else:
            cross_reply_polarity = 0.0

        # Risk 판정 (2개 이상 경고 = high)
        warnings = 0
        if dominant_ratio > 0.70:
            warnings += 1
        if normalized_entropy < 0.50:
            warnings += 1
        if cross_reply_polarity > 0.80:
            warnings += 1

        risk = "high" if warnings >= 2 else "medium" if warnings == 1 else "low"

        result[platform_name] = {
            "risk": risk,
            "entropy": round(normalized_entropy, 3),
            "sentiment_homogeneity": round(dominant_ratio, 3),
            "opinion_diversity": round(normalized_entropy, 3),
            "cross_reply_polarity": round(cross_reply_polarity, 3),
            "dominant_sentiment": dominant,
        }

    return result


def _compute_debate_timeline(
    platform_states: list,
    personas: list,
) -> list:
    """
    reply_count >= 3인 상위 top-level 포스트를 플랫폼당 최대 5개 선택,
    라운드별 sentiment 추이 + 감정 turning point를 반환한다.
    """
    persona_map = {p.node_id: p for p in personas}
    debates = []

    for state in platform_states:
        posts_by_id = {p.id: p for p in state.posts}
        children_map: dict[str, list] = {}
        for p in state.posts:
            if p.parent_id:
                children_map.setdefault(p.parent_id, []).append(p)
        top_level = [p for p in state.posts if p.parent_id is None]

        # reply_count >= 3인 포스트 선정 (reply_count 내림차순 top 5)
        top_level_with_replies = sorted(
            [p for p in top_level if (p.reply_count or 0) >= 3 and p.author_node_id != "__seed__"],
            key=lambda x: (x.reply_count or 0),
            reverse=True,
        )[:5]

        for root_post in top_level_with_replies:
            # 모든 하위 reply 수집 (BFS)
            all_replies: list = []
            queue = deque([root_post.id])
            visited = {root_post.id}
            while queue:
                pid = queue.popleft()
                for child in children_map.get(pid, []):
                    if child.id not in visited:
                        all_replies.append(child)
                        visited.add(child.id)
                        queue.append(child.id)

            # 라운드별 sentiment 집계
            round_sentiment: dict[int, dict[str, int]] = {}
            for r in all_replies:
                s = r.sentiment or "neutral"
                if r.round_num not in round_sentiment:
                    round_sentiment[r.round_num] = {
                        "positive": 0, "neutral": 0, "negative": 0, "constructive": 0,
                    }
                bucket = round_sentiment[r.round_num]
                if s in bucket:
                    bucket[s] += 1

            if not round_sentiment:
                continue

            rounds_sorted = sorted(round_sentiment.keys())
            timeline = []
            prev_pos_pct: float | None = None
            turning_points: list[dict] = []

            for rnd in rounds_sorted:
                sc = round_sentiment[rnd]
                total = sum(sc.values()) or 1
                pos_pct = round(sc["positive"] / total * 100, 1)
                timeline.append({
                    "round": rnd,
                    "positive": sc["positive"],
                    "neutral": sc["neutral"],
                    "negative": sc["negative"],
                    "constructive": sc["constructive"],
                    "positive_pct": pos_pct,
                })
                if prev_pos_pct is not None and abs(pos_pct - prev_pos_pct) >= 20:
                    # 해당 라운드 reply 중 upvotes 최고 포스트를 trigger로 선택
                    round_replies = [r for r in all_replies if r.round_num == rnd]
                    top_reply = max(round_replies, key=lambda x: (x.upvotes or 0), default=None) if round_replies else None
                    turning_points.append({
                        "round": rnd,
                        "direction": "positive" if pos_pct > prev_pos_pct else "negative",
                        "delta_pct": round(pos_pct - prev_pos_pct, 1),
                        "trigger_author": top_reply.author_name if top_reply else None,
                        "trigger_snippet": (top_reply.content or "")[:80] if top_reply else None,
                    })
                prev_pos_pct = pos_pct

            # participant_segments: segment별 참여자 수 집계
            segments: dict[str, int] = {}
            participant_ids = {root_post.author_node_id} | {r.author_node_id for r in all_replies}
            for nid in participant_ids:
                p = persona_map.get(nid)
                if p:
                    seg = _classify_segment(p)
                    segments[seg] = segments.get(seg, 0) + 1

            debates.append({
                "platform": state.platform_name,
                "root_post_id": root_post.id,
                "root_content_snippet": (root_post.content or "")[:120],
                "author_name": root_post.author_name,
                "total_replies": len(all_replies),
                "rounds_active": rounds_sorted,
                "timeline": timeline,
                "turning_points": turning_points,
                "participant_segments": segments,
            })

    return debates


def _enrich_interaction_network(report_json: dict, all_personas: list) -> None:
    """interaction_network 항목에 from_segment, to_segment, sentiment_pattern 필드 추가."""
    if not report_json.get("interaction_network"):
        return
    persona_segment_map: dict[str, str] = {}
    persona_ledger_map: dict[str, dict] = {}
    for p in all_personas:
        seg = _classify_segment(p)
        persona_segment_map[p.node_id] = seg
        persona_ledger_map[p.node_id] = getattr(p, 'interaction_ledger', {}) or {}

    for item in report_json["interaction_network"]:
        from_id = item.get("from", "")
        to_id = item.get("to", "")
        item["from_segment"] = persona_segment_map.get(from_id, "other")
        item["to_segment"] = persona_segment_map.get(to_id, "other")

        # sentiment_pattern: from 페르소나의 ledger에서 to 페르소나와의 최근 교환 패턴
        ledger = persona_ledger_map.get(from_id, {})
        counterpart_data = ledger.get(to_id, {})

        # agree/disagree 비율로 패턴 요약
        agreed = counterpart_data.get("agreed_count", 0)
        disagreed = counterpart_data.get("disagreed_count", 0)
        total = agreed + disagreed
        if total > 0:
            if disagreed > agreed * 2:
                pattern = "debate"
            elif agreed > disagreed * 2:
                pattern = "aligned"
            else:
                pattern = "mixed"
            item["sentiment_pattern"] = pattern
        else:
            item["sentiment_pattern"] = "neutral"


def _compute_response_rates(report_json: dict, all_posts: list) -> None:
    """response_rate, qa_response_rate를 계산하여 report_json에 삽입."""
    if not all_posts:
        return

    # response_rate: reply 포스트 수 / top-level 포스트 수
    reply_posts = [p for p in all_posts if p.parent_id is not None]
    top_level_posts = [p for p in all_posts if p.parent_id is None]
    if top_level_posts:
        report_json["response_rate"] = round(len(reply_posts) / max(len(top_level_posts), 1), 3)
    else:
        report_json["response_rate"] = 0.0

    # qa_response_rate: question 타입 포스트 중 reply_count >= 1인 비율
    question_posts = [p for p in all_posts if "question" in (p.action_type or "").lower()]
    if question_posts:
        answered = sum(1 for p in question_posts if (p.reply_count or 0) >= 1)
        report_json["qa_response_rate"] = round(answered / len(question_posts), 3)
    else:
        report_json["qa_response_rate"] = None


def _compute_environmental_influence(report_json: dict, all_personas: list) -> None:
    """attitude_history에서 특수 트리거(passive_exposure, late_joiner, cross_sync)별 영향 집계."""
    SPECIAL_TRIGGERS = {
        "__passive_exposure__": ("passive_exposure_count", "passive_exposure_total_delta"),
        "__late_joiner_conformity__": ("late_joiner_count", "late_joiner_total_delta"),
        "__cross_sync__": ("cross_sync_count", "cross_sync_total_delta"),
    }
    result: dict[str, int | float] = {
        "passive_exposure_count": 0,
        "passive_exposure_total_delta": 0.0,
        "late_joiner_count": 0,
        "late_joiner_total_delta": 0.0,
        "cross_sync_count": 0,
        "cross_sync_total_delta": 0.0,
    }
    for persona in all_personas:
        for h in getattr(persona, "attitude_history", []):
            trigger = h.get("trigger_post_id", "")
            if trigger in SPECIAL_TRIGGERS:
                count_key, delta_key = SPECIAL_TRIGGERS[trigger]
                result[count_key] += 1
                result[delta_key] = round(result[delta_key] + h.get("delta", 0.0), 4)
    if any(result[k] > 0 for k in ("passive_exposure_count", "late_joiner_count", "cross_sync_count")):
        report_json["environmental_influence"] = result


def _enrich_top_contributors(report_json: dict, all_personas: list) -> None:
    """top_contributors 항목에 segment 필드 추가."""
    if not report_json.get("top_contributors"):
        return
    persona_map = {p.node_id: p for p in all_personas}
    for contributor in report_json["top_contributors"]:
        node_id = contributor.get("node_id", "")
        persona = persona_map.get(node_id)
        if persona:
            contributor["segment"] = _classify_segment(persona)
        else:
            contributor["segment"] = "other"


def _compute_influence_flow(
    all_personas_map: dict,
    all_posts_map: dict,
    classify_fn,
    top_n: int = 20,
) -> list[dict]:
    """attitude_history의 trigger_post_id를 추적하여 영향력 흐름 상위 N개를 반환."""
    flows: list[dict] = []
    for persona in all_personas_map.values():
        for entry in getattr(persona, "attitude_history", []):
            trigger_id = entry.get("trigger_post_id", "")
            if not trigger_id or trigger_id.startswith("__"):
                continue
            post = all_posts_map.get(trigger_id)
            if post is None:
                continue
            influencer = all_personas_map.get(post.author_node_id)
            if influencer is None:
                continue
            if influencer.node_id == persona.node_id:
                continue
            flows.append({
                "influencer_name": influencer.name,
                "influenced_name": persona.name,
                "round": entry.get("round", 0),
                "delta": entry.get("delta", 0.0),
                "trigger_snippet": (post.content or "")[:80],
                "influencer_segment": classify_fn(influencer),
                "influenced_segment": classify_fn(persona),
            })
    flows.sort(key=lambda x: abs(x["delta"]), reverse=True)
    return flows[:top_n]


def _compute_segment_conversion_funnel(
    all_personas_map: dict,
    classify_fn,
) -> dict[str, dict]:
    """세그먼트별 태도 전환 퍼널: converted_positive / negative / neutral 집계."""
    seg_data: dict[str, dict] = {}
    for persona in all_personas_map.values():
        seg = classify_fn(persona)
        if seg not in seg_data:
            seg_data[seg] = {
                "converted_positive": 0,
                "converted_negative": 0,
                "stayed_neutral": 0,
                "total": 0,
                "_rounds_to_convert": [],
            }
        bucket = seg_data[seg]
        bucket["total"] += 1
        shift = getattr(persona, "attitude_shift", 0.0) or 0.0
        if shift >= 0.15:
            bucket["converted_positive"] += 1
            # avg_rounds_to_convert: attitude_history에서 첫 |delta| >= 0.15 항목의 round
            for h in getattr(persona, "attitude_history", []):
                if abs(h.get("delta", 0.0)) >= 0.15:
                    bucket["_rounds_to_convert"].append(h.get("round", 0))
                    break
        elif shift <= -0.15:
            bucket["converted_negative"] += 1
        else:
            bucket["stayed_neutral"] += 1

    result: dict[str, dict] = {}
    for seg, d in seg_data.items():
        total = d["total"] or 1
        rounds_list = d["_rounds_to_convert"]
        result[seg] = {
            "converted_positive": d["converted_positive"],
            "converted_negative": d["converted_negative"],
            "stayed_neutral": d["stayed_neutral"],
            "total": d["total"],
            "conversion_rate": round(d["converted_positive"] / total, 3),
            "resistance_rate": round(d["converted_negative"] / total, 3),
            "avg_rounds_to_convert": round(sum(rounds_list) / len(rounds_list), 1) if rounds_list else None,
        }
    return result


def _compute_unaddressed_concerns(
    all_posts: list,
    all_personas_map: dict,
    platform_map: dict,
    classify_fn,
    top_n: int = 10,
) -> list[dict]:
    """부정적/건설적 감정이지만 답변이 없는 고영향 포스트 top_n개."""
    candidates = [
        p for p in all_posts
        if (p.sentiment or "") in ("negative", "constructive")
        and (p.reply_count is None or p.reply_count == 0)
    ]
    candidates.sort(key=lambda x: x.weighted_score or 0.0, reverse=True)
    results: list[dict] = []
    for post in candidates[:top_n]:
        author_seg = "unknown"
        if post.author_node_id and post.author_node_id in all_personas_map:
            author_seg = classify_fn(all_personas_map[post.author_node_id])
        results.append({
            "post_id": post.id,
            "platform": post.platform,
            "author_name": post.author_name,
            "author_segment": author_seg,
            "content_snippet": (post.content or "")[:100],
            "sentiment": post.sentiment,
            "weighted_score": post.weighted_score or 0.0,
        })
    return results


def _compute_qa_pairs(
    all_posts: list,
    children_map: dict,
    question_actions: set[str],
) -> list[dict]:
    """질문형 포스트와 그 답변을 매칭하여 Q&A 쌍 목록 반환."""
    qa_list: list[dict] = []
    for post in all_posts:
        if (post.action_type or "") not in question_actions:
            continue
        children = children_map.get(post.id, [])
        answers = sorted(children, key=lambda c: c.upvotes or 0, reverse=True)[:3]
        qa_list.append({
            "question_id": post.id,
            "question_text": (post.content or "")[:200],
            "platform": post.platform,
            "author_name": post.author_name,
            "answers": [
                {"text": (a.content or "")[:150], "author_name": a.author_name, "upvotes": a.upvotes or 0}
                for a in answers
            ],
            "answered": len(answers) > 0,
        })
    # answered=True를 앞에, False를 뒤에
    qa_list.sort(key=lambda x: (not x["answered"],))
    return qa_list


def _check_convergence(round_sentiments: list[dict]) -> float:
    """최근 2라운드의 sentiment 비율 변화를 0~1 수렴 점수로 반환 (1.0 = 완전 수렴)"""
    if len(round_sentiments) < 2:
        return 0.0
    prev = round_sentiments[-2]
    curr = round_sentiments[-1]
    total_prev = max(prev.get("positive", 0) + prev.get("neutral", 0) + prev.get("negative", 0), 1)
    total_curr = max(curr.get("positive", 0) + curr.get("neutral", 0) + curr.get("negative", 0), 1)
    delta_pos = abs(curr.get("positive", 0) / total_curr - prev.get("positive", 0) / total_prev)
    delta_neg = abs(curr.get("negative", 0) / total_curr - prev.get("negative", 0) / total_prev)
    delta_neu = abs(curr.get("neutral", 0) / total_curr - prev.get("neutral", 0) / total_prev)
    max_delta = max(delta_pos, delta_neg, delta_neu)
    return max(0.0, 1.0 - max_delta * 10)  # 10%p 변화 = 0 수렴점수


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


def _coerce_str_list(value: object) -> list[str]:
    if isinstance(value, str):
        return [
            part.strip()
            for part in value.replace("\n", ",").replace(";", ",").split(",")
            if part.strip()
        ]
    if isinstance(value, list):
        return [str(part).strip() for part in value if str(part).strip()]
    return []


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
                seniority=str(d.get("seniority", "") or "").lower().strip(),
                affiliation=str(d.get("affiliation", "")),
                company=str(d.get("company", "")),
                mbti=str(d.get("mbti", "")),
                interests=_coerce_str_list(d.get("interests")),
                skepticism=_coerce_int(d.get("skepticism"), 5),
                commercial_focus=_coerce_int(d.get("commercial_focus"), 5),
                innovation_openness=_coerce_int(d.get("innovation_openness"), 5),
                source_title=str(d.get("source_title", "")),
                domain_type=str(d.get("domain_type", "")),
                tech_area=_coerce_str_list(d.get("tech_area")),
                market=_coerce_str_list(d.get("market")),
                problem_domain=_coerce_str_list(d.get("problem_domain")),
                jtbd=str(d.get("jtbd", "")),
                cognitive_pattern=str(d.get("cognitive_pattern", "")),
                emotional_state=str(d.get("emotional_state", "")),
                region=str(d.get("region", "")),
                initial_emotional_state=str(d.get("initial_emotional_state", d.get("emotional_state", ""))),
                attitude_shift=float(d.get("attitude_shift") or 0.0),
                attitude_history=[h for h in d.get("attitude_history", []) if isinstance(h, dict)],
                interaction_ledger=dict(d.get("interaction_ledger", {})),
                persuasion_memory=list(d.get("persuasion_memory", [])),
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
                reply_count=_coerce_int(p.get("reply_count"), 0),
                structured_data=p.get("structured_data", {}),
                sentiment=str(p.get("sentiment", "")),
                weighted_score=float(p.get("weighted_score") or 0.0),
                vote_rounds=list(p.get("vote_rounds", [])),
                voters=list(p.get("voters", [])),
                endorsed_by=list(p.get("endorsed_by", [])),
            )
            for p in state_d.get("posts", [])
            if isinstance(p, dict)
        ]
        state = PlatformState(
            platform_name=str(state_d.get("platform_name", platform_name)),
            posts=posts,
            round_num=_coerce_int(state_d.get("round_num"), 0),
            recent_speakers=dict(state_d.get("recent_speakers") or {}),
            mentioned_agents=dict(state_d.get("mentioned_agents") or {}),
        )
        state._rebuild_count = 0  # Reset after restoration so runtime rebuilds are tracked accurately
        result[platform_name] = state
    return result


async def run_simulation(
    input_text: str,
    context_nodes: list[dict],
    domain: str,
    max_agents: int = 30,
    num_rounds: int = 8,
    platforms: list[str] | None = None,
    language: str = "English",
    edges: list[dict] | None = None,
    activation_rate: float = 0.25,
    checkpoint: dict | None = None,
    seed_text: str | None = None,
) -> AsyncGenerator[dict, None]:
    nodes = context_nodes  # alias for rest of function body
    idea_text = input_text  # alias for rest of function body
    seed_idea = seed_text or input_text  # seed posts use original text if provided
    platform_personas: dict[str, list[Persona]] = {}
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

    # 모든 클러스터의 문서를 합쳐서 각 페르소나에게 공유
    # _build_prior_knowledge가 relevance 점수로 top-5를 뽑으므로
    # 클러스터 크기에 관계없이 모든 페르소나가 풍부한 사전지식을 가짐
    all_context_docs = [node for c in clusters for node in c["nodes"]]
    cluster_docs_map: dict[str, list[dict]] = {c["id"]: all_context_docs for c in clusters}

    yield {"type": "sim_start", "agent_count": len(clusters)}

    if checkpoint is not None:
        # --- RESUME PATH ---
        platform_personas = _restore_personas(checkpoint.get("personas", {}))
        platform_states = _restore_platform_states(checkpoint.get("platform_states", {}))
        start_round = _coerce_int(checkpoint.get("last_round"), 0) + 1
        yield {"type": "sim_resume", "from_round": start_round}

        # 이전 라운드 personas 재발행
        for platform_name, personas_list in platform_personas.items():
            for p in personas_list:
                yield {
                    "type": "sim_persona",
                    "node_id": p.node_id,
                    "platform": platform_name,
                    "persona": {
                        "name": p.name,
                        "role": p.role,
                        "age": p.age,
                        "generation": p.generation,
                        "seniority": p.seniority,
                        "affiliation": p.affiliation,
                        "company": p.company,
                        "mbti": p.mbti,
                        "interests": p.interests,
                        "skepticism": p.skepticism,
                        "commercial_focus": p.commercial_focus,
                        "innovation_openness": p.innovation_openness,
                        "source_title": p.source_title,
                        "domain_type": p.domain_type,
                        "tech_area": p.tech_area,
                        "market": p.market,
                        "problem_domain": p.problem_domain,
                        "jtbd": p.jtbd,
                        "cognitive_pattern": p.cognitive_pattern,
                        "emotional_state": p.emotional_state,
                        "region": getattr(p, 'region', ''),
                        "attitude_shift": getattr(p, 'attitude_shift', 0.0),
                        "attitude_history": getattr(p, 'attitude_history', []),
                        "interaction_ledger": getattr(p, 'interaction_ledger', {}),
                        "persuasion_memory": getattr(p, 'persuasion_memory', []),
                    },
                }

        # 이전 라운드 posts 재발행
        for platform_name, state in platform_states.items():
            for post in state.posts:
                yield {
                    "type": "sim_platform_post",
                    "platform": platform_name,
                    "post": dataclasses.asdict(post),
                }
    else:
        # --- NORMAL PATH ---
        # Persona generation: all platforms run in parallel, events streamed in real-time
        platform_personas = {p.name: [] for p in active_platforms}
        results_by_platform: dict[str, list[tuple[dict, "Persona | None"]]] = {}
        persona_event_queue: asyncio.Queue = asyncio.Queue()

        # Extract top entity names from context nodes for competitor awareness
        _entity_counts: dict[str, int] = {}
        for _doc in all_context_docs:
            for _ent in (_doc.get("_entities") or []):
                _ent_lower = str(_ent).strip()
                if _ent_lower:
                    _entity_counts[_ent_lower] = _entity_counts.get(_ent_lower, 0) + 1
        _top_entities = sorted(_entity_counts, key=_entity_counts.get, reverse=True)[:5]
        _competitor_context = ", ".join(_top_entities) if _top_entities else ""

        # --- Pool-based persona pre-selection ---
        # Try to load the agent pool. If available, use pool-based selection (no per-agent LLM calls).
        # If the pool is unavailable, fall back to original LLM-based generation.
        _agent_pool = load_agent_pool()
        _pool_available = bool(_agent_pool)
        _pre_assigned_by_platform: dict[str, list[dict] | None] = {p.name: None for p in active_platforms}

        if _pool_available:
            try:
                _platform_names = [p.name for p in active_platforms]
                _distributions = await get_distribution(idea_text, _platform_names, _llm)
                _used_names: set[str] = set()
                for _plat in active_platforms:
                    _dist = _distributions.get(_plat.name, {})
                    _pre_assigned_by_platform[_plat.name] = select_agents_for_platform(
                        platform=_plat.name,
                        n=len(clusters),
                        distribution=_dist,
                        pool=_agent_pool,
                        used_names=_used_names,
                    )
                logger.info(
                    "Pool-based persona selection complete for %d platforms (%d agents each)",
                    len(active_platforms), len(clusters),
                )
            except Exception as _pool_exc:
                logger.warning(
                    "Pool-based persona selection failed (%s) — falling back to LLM generation",
                    _pool_exc,
                )
                _pre_assigned_by_platform = {p.name: None for p in active_platforms}

        async def collect_personas_for_platform(platform_name: str) -> None:
            results = []
            _pre_assigned = _pre_assigned_by_platform.get(platform_name)
            try:
                async for event in round_personas(
                    clusters, idea_text,
                    platform_name=platform_name,
                    domain_info=domain,
                    competitor_context=_competitor_context,
                    pre_assigned_personas=_pre_assigned,
                ):
                    persona = event.pop("_persona", None)
                    results.append((event, persona))
                    await persona_event_queue.put(event)
            except Exception as exc:
                logger.warning("Persona generation failed for platform %s: %s", platform_name, exc)
            finally:
                results_by_platform[platform_name] = results
                await persona_event_queue.put(None)  # sentinel

        persona_tasks = [
            asyncio.create_task(collect_personas_for_platform(p.name))
            for p in active_platforms
        ]
        remaining = len(persona_tasks)
        while remaining > 0:
            item = await persona_event_queue.get()
            if item is None:
                remaining -= 1
            else:
                yield item

        # Deduplicate names and build platform_personas after all events are streamed
        for platform_name, entries in results_by_platform.items():
            _deduplicate_names(entries)
            for _event, persona in entries:
                if persona is not None:
                    platform_personas[platform_name].append(persona)

        # Post-generation distribution validation: ensure skepticism/region/MBTI diversity
        for platform_name, personas_list in platform_personas.items():
            if personas_list:
                _validate_persona_distribution(personas_list)

        if not any(platform_personas.values()):
            yield {"type": "sim_error", "message": "Persona generation failed for all platforms"}
            yield {"type": "sim_done"}
            return

        # Round 0: seed posts for each platform (parallel)
        platform_states: dict[str, PlatformState] = {}
        seed_tasks = {
            p.name: asyncio.create_task(generate_seed_post(p, seed_idea, language))
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

    # Accumulate segment distributions per round for report
    # Convergence tracking
    convergence_round: int | None = None
    early_exit_round: int | None = None
    consecutive_convergence: int = 0
    early_converging: bool = False

    if checkpoint is not None:
        # Restore runner state accumulated from previous rounds
        _rs = checkpoint.get("runner_state") or {}
        round_segment_distributions: dict[int, dict] = {
            int(k): v for k, v in (_rs.get("round_segment_distributions") or {}).items()
        }
        round_action_type_distributions: dict[int, dict] = {
            int(k): v for k, v in (_rs.get("round_action_type_distributions") or {}).items()
        }
        round_sentiments: list[dict] = list(_rs.get("round_sentiments") or [])
        convergence_counter: int = int(_rs.get("convergence_counter", 0))
        consecutive_convergence = int(_rs.get("consecutive_convergence", 0))
        early_converging = bool(_rs.get("early_converging", False))
        round_pass_counts: dict[int, int] = {
            int(k): v for k, v in (_rs.get("round_pass_counts") or {}).items()
        }
        round_inactive_counts: dict[int, int] = {
            int(k): v for k, v in (_rs.get("round_inactive_counts") or {}).items()
        }
    else:
        round_segment_distributions: dict[int, dict] = {}
        round_action_type_distributions: dict[int, dict] = {}
        round_sentiments: list[dict] = []
        convergence_counter: int = 0
        round_pass_counts: dict[int, int] = {}
        round_inactive_counts: dict[int, int] = {}

    # Per-platform activation rate tracking: starts at the user-specified rate,
    # then each round's dynamic adjustment persists to the next round.
    adjusted_rates: dict[str, float] = {p.name: activation_rate for p in active_platforms}

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
            plat_rate = adjusted_rates.get(plat.name, activation_rate)
            async for event in platform_round(
                plat, state, plat_personas, idea_text, rn, language, plat_rate,
                cluster_docs_map=cluster_docs_map,
                total_rounds=num_rounds,
                all_platform_states=platform_states,
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

        # Update per-platform activation rates from this round's dynamic adjustment
        for plat_name, stats in round_summary_stats.items():
            if "adjusted_activation_rate" in stats:
                adjusted_rates[plat_name] = stats["adjusted_activation_rate"]

        # Compute top_discussed_post_id per platform for this round
        for pname, pstate in platform_states.items():
            reply_count: dict[str, int] = {}
            for post in pstate.posts:
                if post.round_num == round_num and post.parent_id is not None:
                    reply_count[post.parent_id] = reply_count.get(post.parent_id, 0) + 1
            top_discussed = max(reply_count, key=reply_count.get) if reply_count else None
            if pname in round_summary_stats:
                round_summary_stats[pname]["top_discussed_post_id"] = top_discussed

        failed = sum(1 for r in results if isinstance(r, Exception))
        if 0 < failed and failed * 2 <= len(active_platforms):
            yield {"type": "sim_warning",
                   "message": f"{failed} platform(s) failed this round but simulation continues"}
        if failed * 2 > len(active_platforms):
            yield {"type": "sim_error",
                   "message": f"Too many platforms failed ({failed}/{len(active_platforms)})"}
            yield {"type": "sim_done"}
            return

        # Merge segment_distribution across all platforms for this round
        merged_seg_dist: dict[str, int] = {}
        for _pname, _pstats in round_summary_stats.items():
            for seg, count in _pstats.get("segment_distribution", {}).items():
                merged_seg_dist[seg] = merged_seg_dist.get(seg, 0) + count
        round_segment_distributions[round_num] = merged_seg_dist

        # Merge action_type_distribution across all platforms and accumulate for report
        merged_action_dist: dict[str, int] = {}
        for stats in round_summary_stats.values():
            for at, cnt in stats.get("action_type_distribution", {}).items():
                merged_action_dist[at] = merged_action_dist.get(at, 0) + cnt
        round_action_type_distributions[round_num] = merged_action_dist.copy() if merged_action_dist else {}

        # Aggregate pass_count and inactive_count across platforms
        total_pass_count = sum(stats.get("pass_count", 0) for stats in round_summary_stats.values())
        total_inactive_count = sum(stats.get("inactive_count", 0) for stats in round_summary_stats.values())
        round_pass_counts[round_num] = total_pass_count
        round_inactive_counts[round_num] = total_inactive_count

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
            "raw_items": [],    # tasks.py fills in the real value when saving
            "runner_state": {
                "round_segment_distributions": round_segment_distributions,
                "round_action_type_distributions": round_action_type_distributions,
                "round_sentiments": round_sentiments,
                "convergence_counter": convergence_counter,
                "consecutive_convergence": consecutive_convergence,
                "early_converging": early_converging,
                "round_pass_counts": round_pass_counts,
                "round_inactive_counts": round_inactive_counts,
            },
        }

        # Aggregate sentiment counts across platforms for convergence check
        merged_sentiment: dict[str, int] = {"positive": 0, "neutral": 0, "negative": 0}
        for stats in round_summary_stats.values():
            sent_dist = stats.get("sentiment_distribution", {})
            for key in merged_sentiment:
                merged_sentiment[key] += sent_dist.get(key, 0)
        round_sentiments.append(merged_sentiment)

        convergence_score = _check_convergence(round_sentiments)

        yield {
            "type": "sim_round_summary",
            "round_num": round_num,
            "platform_summaries": round_summary_stats,
            "segment_distribution": merged_seg_dist,
            "action_type_distribution": merged_action_dist,
            "pass_count": total_pass_count,
            "inactive_count": total_inactive_count,
            "convergence_score": convergence_score,
        }

        # Convergence early-stop check
        if convergence_score >= 0.85:
            convergence_counter += 1
        else:
            convergence_counter = 0

        if convergence_counter >= 3 and round_num > num_rounds // 2:
            yield {
                "type": "sim_early_stop",
                "reason": "convergence",
                "stopped_at_round": round_num,
                "convergence_score": convergence_score,
            }
            convergence_round = round_num
            break

        # ── Early exit on consensus: 2-tier gradual shutdown ──
        # Only eligible after 70% of total rounds to prevent premature exit
        if convergence_score >= 0.85 and round_num >= num_rounds * 0.7:
            consecutive_convergence += 1
            if consecutive_convergence == 1:
                # 1st detection: halve activation_rate (floor 0.10) for next round
                early_converging = True
                for plat_name in adjusted_rates:
                    adjusted_rates[plat_name] = max(0.10, adjusted_rates[plat_name] * 0.5)
            if consecutive_convergence >= 2:
                # 2nd consecutive detection: immediate exit
                yield {
                    "type": "sim_progress",
                    "message": f"Consensus detected at round {round_num} — generating report",
                    "round": round_num,
                    "early_exit": True,
                }
                early_exit_round = round_num
                convergence_round = convergence_round or round_num
                break
        else:
            consecutive_convergence = 0
            early_converging = False

        # ── Cross-platform attitude contagion (decay factor 0.3) ──
        # Build O(1) lookup map: (platform_name, node_id) -> Persona
        platform_persona_map: dict[tuple[str, str], Persona] = {
            (plat_name, p.node_id): p
            for plat_name, personas in platform_personas.items()
            for p in personas
        }

        # Build node_id -> list of attitude_shifts across platforms
        node_shifts: dict[str, list[tuple[str, float]]] = defaultdict(list)
        for p_name, p_list in platform_personas.items():
            for persona in p_list:
                node_shifts[persona.node_id].append((p_name, persona.attitude_shift))

        for node_id, shifts in node_shifts.items():
            if len(shifts) < 2:
                continue
            # Weighted mean shift: seniority에 따라 영향력 차등 반영
            weighted_sum = 0.0
            weight_total = 0.0
            for p_name_s, shift_val in shifts:
                # O(1) 딕셔너리 룩업으로 페르소나 참조
                _p = platform_persona_map.get((p_name_s, node_id))
                w = _SENIORITY_WEIGHTS.get(
                    getattr(_p, "seniority", "mid"), 1.0
                ) if _p else 1.0
                weighted_sum += shift_val * w
                weight_total += w
            mean_shift = weighted_sum / weight_total if weight_total > 0 else 0.0
            for p_name_s, _shift_val in shifts:
                persona = platform_persona_map.get((p_name_s, node_id))
                if persona is None:
                    continue
                own = persona.attitude_shift
                synced = own * 0.7 + mean_shift * 0.3
                delta = synced - own
                if abs(delta) > 0.005:
                    persona.attitude_shift = synced
                    persona.attitude_history.append({
                        "round": round_num,
                        "delta": round(delta, 4),
                        "trigger_post_id": "__cross_sync__",
                    })

    # Final report
    try:
        # Build node_id -> Persona mapping for author metadata in report
        all_personas: dict[str, Persona] = {}
        for personas_list in platform_personas.values():
            for p in personas_list:
                all_personas[p.node_id] = p
        report_json, report_md = await generate_report(
            list(platform_states.values()), idea_text, domain, language,
            personas=all_personas,
            round_segment_distributions=round_segment_distributions,
            round_action_type_distributions=round_action_type_distributions,
            total_agent_count=len(all_personas),
            convergence_round=convergence_round,
            round_pass_counts=round_pass_counts,
            round_inactive_counts=round_inactive_counts,
        )
        report_json["early_exit_round"] = early_exit_round  # None if completed normally
        report_json["echo_chamber_risk"] = _compute_echo_chamber_risk(
            list(platform_states.values()), {}
        )
        all_personas_flat = [p for plist in platform_personas.values() for p in plist]
        report_json["debate_timeline"] = _compute_debate_timeline(
            list(platform_states.values()), all_personas_flat
        )
        _enrich_interaction_network(report_json, all_personas_flat)
        all_posts_flat = [p for state in platform_states.values() for p in state.posts]
        _compute_response_rates(report_json, all_posts_flat)
        _enrich_top_contributors(report_json, all_personas_flat)
        _compute_environmental_influence(report_json, all_personas_flat)

        # C51-3: Influence flow
        all_posts_map_flat = {p.id: p for state in platform_states.values() for p in state.posts}
        all_personas_map_flat = {p.node_id: p for p in all_personas_flat}

        report_json["influence_flow"] = _compute_influence_flow(
            all_personas_map_flat, all_posts_map_flat, _classify_segment
        )

        # C51-4: Segment conversion funnel
        report_json["segment_conversion_funnel"] = _compute_segment_conversion_funnel(
            all_personas_map_flat, _classify_segment
        )

        # C51-5: Unaddressed concerns
        report_json["unaddressed_concerns"] = _compute_unaddressed_concerns(
            all_posts_flat, all_personas_map_flat, {}, _classify_segment
        )

        # C51-6: QA pairs
        children_map_global: dict = {}
        for _p in all_posts_flat:
            if _p.parent_id:
                children_map_global.setdefault(_p.parent_id, []).append(_p)

        QUESTION_ACTIONS = {"ask", "question", "ask_question", "ask_hn", "ask_advice"}
        report_json["qa_pairs"] = _compute_qa_pairs(
            all_posts_flat, children_map_global, QUESTION_ACTIONS
        )

        # archetype_narratives에 platform_breakdown 추가
        if report_json.get("archetype_narratives") and all_personas_flat:
            from collections import defaultdict as _dd
            seg_plat_deltas: dict = _dd(lambda: _dd(list))
            for _plat_name, _plat_personas in platform_personas.items():
                for _p in _plat_personas:
                    _seg = _classify_segment(_p)
                    if _seg and _plat_name:
                        seg_plat_deltas[_seg][_plat_name].append(getattr(_p, 'attitude_shift', 0.0) or 0.0)
            for item in report_json["archetype_narratives"]:
                seg = item.get("segment", "")
                if seg in seg_plat_deltas:
                    item["platform_breakdown"] = {
                        plat: round(sum(deltas) / len(deltas), 3)
                        for plat, deltas in seg_plat_deltas[seg].items()
                        if deltas
                    }

        # ProductHunt star rating 집계
        ph_posts_with_ratings: list[int] = []
        for state in platform_states.values():
            if state.platform_name == "producthunt":
                for post in state.posts:
                    rating = (post.structured_data or {}).get("rating")
                    if rating is not None:
                        try:
                            ph_posts_with_ratings.append(int(rating))
                        except (ValueError, TypeError):
                            pass
                break

        if ph_posts_with_ratings:
            from collections import Counter as _Counter
            dist = _Counter(ph_posts_with_ratings)
            report_json["producthunt_ratings"] = {
                "avg_rating": round(sum(ph_posts_with_ratings) / len(ph_posts_with_ratings), 2),
                "distribution": {str(i): dist.get(i, 0) for i in range(1, 6)},
                "total_reviews": len(ph_posts_with_ratings),
            }

        # ProductHunt pros/cons 집계
        ph_pros: list[str] = []
        ph_cons: list[str] = []
        for state in platform_states.values():
            if state.platform_name == "producthunt":
                for post in state.posts:
                    sd = post.structured_data or {}
                    for item in sd.get("pros", []):
                        if isinstance(item, str) and item.strip():
                            ph_pros.append(item.strip().lower())
                    for item in sd.get("cons", []):
                        if isinstance(item, str) and item.strip():
                            ph_cons.append(item.strip().lower())
                break

        if ph_pros or ph_cons:
            from collections import Counter as _Counter2
            def _top_themes(items: list[str], n: int = 5) -> list[dict]:
                counts = _Counter2(items)
                return [{"theme": t, "count": c} for t, c in counts.most_common(n)]

            report_json["producthunt_pros_cons"] = {
                "top_pros": _top_themes(ph_pros),
                "top_cons": _top_themes(ph_cons),
            }

        # ProductHunt rating-sentiment 불일치 탐지
        rating_sentiment_matrix: dict[str, dict[str, int]] = {}
        mismatch_count = 0
        total_ph_reviews = 0
        for state in platform_states.values():
            if state.platform_name == "producthunt":
                for post in state.posts:
                    sd = post.structured_data or {}
                    rating = sd.get("rating")
                    if rating is None:
                        continue
                    try:
                        rating_int = int(rating)
                    except (ValueError, TypeError):
                        continue
                    total_ph_reviews += 1
                    sentiment = post.sentiment or "neutral"
                    key = str(rating_int)
                    if key not in rating_sentiment_matrix:
                        rating_sentiment_matrix[key] = {}
                    rating_sentiment_matrix[key][sentiment] = rating_sentiment_matrix[key].get(sentiment, 0) + 1
                    if (rating_int >= 4 and sentiment in {"negative", "constructive"}) or (rating_int <= 2 and sentiment == "positive"):
                        mismatch_count += 1
                break

        if total_ph_reviews > 0:
            mismatch_rate = round(mismatch_count / max(total_ph_reviews, 1), 3)
            report_json["producthunt_rating_sentiment_matrix"] = {
                "matrix": rating_sentiment_matrix,
                "mismatch_rate": mismatch_rate,
                "mismatch_count": mismatch_count,
                "total_reviews": total_ph_reviews,
            }
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
                        "sentiment": p.sentiment,
                        "weighted_score": p.weighted_score,
                        "reply_count": p.reply_count,
                        "vote_rounds": list(p.vote_rounds) if p.vote_rounds else [],
                        "voters": list(p.voters) if p.voters else [],
                        "structured_data": p.structured_data if hasattr(p, 'structured_data') else None,
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
                        "source_title": p.source_title,
                        "domain_type": p.domain_type,
                        "tech_area": p.tech_area,
                        "market": p.market,
                        "problem_domain": p.problem_domain,
                        "jtbd": p.jtbd,
                        "cognitive_pattern": p.cognitive_pattern,
                        "emotional_state": p.emotional_state,
                        "region": getattr(p, 'region', ''),
                        "attitude_shift": getattr(p, 'attitude_shift', 0.0),
                        "attitude_history": getattr(p, 'attitude_history', []),
                        "interaction_ledger": getattr(p, 'interaction_ledger', {}),
                        "persuasion_memory": getattr(p, 'persuasion_memory', []),
                    }
                    for p in personas_list
                ]
                for name, personas_list in platform_personas.items()
            },
        },
    }
    yield {"type": "sim_done"}
