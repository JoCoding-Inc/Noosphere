from __future__ import annotations
import dataclasses
from typing import TYPE_CHECKING
from backend.simulation.models import SocialPost, PlatformState

if TYPE_CHECKING:
    from backend.simulation.models import Persona


@dataclasses.dataclass
class AgentAction:
    action_type: str
    target_post_id: str | None   # None for new top-level posts


_SENIOR_ENDORSERS = {'director', 'vp', 'c_suite'}


class AbstractPlatform:
    name: str
    allowed_actions: list[str]
    no_content_actions: set[str]
    system_prompt: str           # Platform persona for LLM
    seed_controversy_hint: str = ""

    def requires_content(self, action_type: str) -> bool:
        return action_type not in self.no_content_actions

    def get_allowed_actions(self, persona: "Persona") -> list[str]:
        """Restrict action types based on persona attributes (e.g. maker_response)."""
        return list(self.allowed_actions)

    def content_tool(self, action_type: str) -> dict:
        """Return a structured output tool definition for the given action type."""
        return {
            "name": "create_content",
            "description": f"Write a {action_type} for {self.name}.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Content text"},
                    "sentiment": {
                        "type": "string",
                        "enum": ["positive", "neutral", "negative", "constructive"],
                        "description": "Overall sentiment of this post toward the idea being discussed",
                    },
                },
                "required": ["text", "sentiment"],
            },
        }

    def seed_tool(self) -> dict:
        """Return a structured output tool definition for the seed post."""
        return {
            "name": "create_seed_post",
            "description": f"Write the opening post introducing an idea on {self.name}.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Opening post text"},
                },
                "required": ["text"],
            },
        }

    def extract_content(self, action_type: str, structured_data: dict) -> str:
        """Extract a display-friendly text string from structured_data."""
        return structured_data.get("text", "")

    def extract_seed_content(self, structured_data: dict) -> str:
        """Extract display text from seed post structured_data."""
        return structured_data.get("text", "")

    def build_feed(
        self,
        state: PlatformState,
        top_posts: int = 5,
        top_comments_per_post: int = 3,
        max_feed_chars: int = 2800,
        round_num: int = 0,
        personas_map: dict | None = None,
        total_rounds: int = 8,
        children_map: dict | None = None,
    ) -> str:
        """Render platform feed as text for LLM context.

        Uses a pre-built children_map for O(n) lookup instead of O(n^2) repeated scans.
        In late rounds (phase_ratio > 0.66), cap comments per post to 2 to save tokens.
        """
        # Late-round comment cap: reduce from default to 2 in synthesis phase
        phase_ratio = round_num / max(total_rounds, 1)
        if phase_ratio > 0.66:
            top_comments_per_post = min(top_comments_per_post, 2)
            max_feed_chars = min(max_feed_chars, 2200)
        # Build children_map once: parent_id -> list of child posts
        if children_map is None:
            children_map: dict[str | None, list[SocialPost]] = {}
            for p in state.posts:
                children_map.setdefault(p.parent_id, []).append(p)
        elif None not in children_map:
            # 외부 주입 children_map에 None 키가 없으면 top-level 포스트 보충
            children_map = dict(children_map)
            for p in state.posts:
                if p.parent_id is None:
                    children_map.setdefault(None, []).append(p)

        top_level = children_map.get(None, [])

        # Determine HOT TOPIC posts: reply_count >= 3, or the single most-replied post
        hot_threshold = 3
        max_reply = max((p.reply_count for p in top_level), default=0)
        hot_ids: set[str] = set()
        for p in top_level:
            if p.reply_count >= hot_threshold or (max_reply >= 1 and p.reply_count == max_reply):
                hot_ids.add(p.id)

        # Seniority bonus for feed sort: opinion leaders surface higher
        _SENIORITY_BONUS = {
            'c_suite': 1.5, 'vp': 1.3, 'director': 1.1,
            'principal': 1.0, 'lead': 0.8,
        }

        # Split into current round and earlier posts, HOT TOPIC posts sorted first
        # Alternating sort: even rounds by net votes + momentum, odd rounds by reply_count
        def _sort_key(p: SocialPost) -> tuple:
            # seniority bonus from personas_map
            _author = personas_map.get(p.author_node_id) if personas_map else None
            _sen = getattr(_author, 'seniority', '') or ''
            sen_bonus = _SENIORITY_BONUS.get(_sen, 0)

            if round_num % 2 == 1:
                return (0 if p.id in hot_ids else 1, -(p.reply_count + sen_bonus))
            # vote_rounds에서 최근 2라운드 투표 모멘텀 계산
            vote_rounds_list = getattr(p, 'vote_rounds', [])
            recent_votes = sum(1 for r in vote_rounds_list if round_num > 0 and r >= round_num - 2)
            total_votes = len(vote_rounds_list)
            momentum_bonus = recent_votes if total_votes > 0 else 0
            net = p.upvotes - p.downvotes
            sort_val = net + momentum_bonus * 1.5 + sen_bonus
            return (0 if p.id in hot_ids else 1, -sort_val)

        current_round_posts = sorted(
            [p for p in top_level if p.round_num == state.round_num],
            key=_sort_key,
        )[:top_posts]
        earlier_posts = sorted(
            [p for p in top_level if p.round_num != state.round_num],
            key=_sort_key,
        )[:top_posts]

        # Sentiment summary at the top of the feed
        sentiment_counts: dict[str, int] = {"positive": 0, "neutral": 0, "negative": 0, "constructive": 0}
        for p in state.posts:
            if p.author_node_id == "__seed__":
                continue
            s = getattr(p, "sentiment", "") or ""
            if s in sentiment_counts:
                sentiment_counts[s] += 1
        sentiment_line = (
            f"Feed sentiment: {sentiment_counts['positive']} positive, "
            f"{sentiment_counts['neutral']} neutral, "
            f"{sentiment_counts['negative']} negative, "
            f"{sentiment_counts['constructive']} constructive"
        )

        # Sentiment trend delta hint (round >= 3)
        sentiment_trend = ""
        if round_num >= 3:
            recent_posts = [p for p in state.posts if getattr(p, 'round_num', 0) >= round_num - 2 and p.author_node_id != "__seed__"]
            older_posts = [p for p in state.posts if getattr(p, 'round_num', 0) < round_num - 2 and p.author_node_id != "__seed__"]
            if recent_posts and older_posts:
                recent_pos_pct = sum(1 for p in recent_posts if getattr(p, 'sentiment', '') == 'positive') / len(recent_posts) * 100
                older_pos_pct = sum(1 for p in older_posts if getattr(p, 'sentiment', '') == 'positive') / len(older_posts) * 100
                delta = recent_pos_pct - older_pos_pct
                if abs(delta) >= 8:
                    direction = "\u25b2" if delta > 0 else "\u25bc"
                    sentiment_trend = f"[TREND] Sentiment {direction}{abs(delta):.0f}% {'more positive' if delta > 0 else 'more negative'} in recent rounds"

        lines: list[str] = [
            f"=== {self.name.upper()} FEED (Round {state.round_num}) ===",
        ]
        if sentiment_trend:
            lines.append(sentiment_trend)
        lines.append(sentiment_line)
        comment_ids: list[str] = []
        reply_ids: list[str] = []

        def _render_post(post: SocialPost) -> tuple[str, list[str], list[str]]:
            """Render a post and its comments/replies.

            Returns (rendered_text, comment_ids_collected, reply_ids_collected).
            """
            _comment_ids: list[str] = []
            _reply_ids: list[str] = []
            _lines: list[str] = []
            hot_tag = "[HOT TOPIC] " if post.id in hot_ids else ""
            reply_info = f" ({post.reply_count} replies)" if post.reply_count > 0 else ""
            # Resolve author label with role/affiliation if persona is available
            author_label = post.author_name
            if personas_map:
                _persona = personas_map.get(post.author_node_id)
                if _persona:
                    author_label = f"{_persona.name} ({_persona.role} · {_persona.affiliation})"
            # trending 판단: vote_rounds가 있고, 최근 2라운드에서 받은 투표 비율 >= 50%
            vote_rounds = getattr(post, 'vote_rounds', [])
            if vote_rounds and round_num > 2:
                recent_votes = sum(1 for r in vote_rounds if r >= round_num - 2)
                if len(vote_rounds) > 0 and recent_votes / len(vote_rounds) >= 0.5 and len(vote_rounds) >= 3:
                    trend_tag = " [TRENDING UP]"
                elif post.upvotes == 0 and round_num - getattr(post, 'round_num', round_num) >= 3:
                    trend_tag = " [FADING]"
                else:
                    trend_tag = ""
            else:
                trend_tag = ""
            # [FADING]: vote_rounds 없고 오래된 low-engagement 포스트
            if not trend_tag and not vote_rounds and post.upvotes == 0:
                post_round = getattr(post, 'round_num', round_num)
                if round_num - post_round >= 3:
                    trend_tag = " [FADING]"
            # Sentiment label: [+] positive, [-] negative, [~] neutral/constructive, omit if absent
            _sent = getattr(post, "sentiment", "") or ""
            if _sent == "positive":
                sent_tag = " [+]"
            elif _sent == "negative":
                sent_tag = " [-]"
            elif _sent in ("neutral", "constructive"):
                sent_tag = " [~]"
            else:
                sent_tag = ""
            endorsed_tag = " [ENDORSED]" if getattr(post, 'endorsed_by', []) else ""
            _lines.append(
                f"\n{hot_tag}[POST id={post.id}] {author_label} (+{post.upvotes}/-{post.downvotes}){reply_info}{trend_tag}{sent_tag}{endorsed_tag}\n"
                f"{post.content[:300]}"
            )
            comments = children_map.get(post.id, [])
            comments_sorted = sorted(comments, key=lambda p: -p.upvotes)[:top_comments_per_post]
            for c in comments_sorted:
                _comment_ids.append(c.id)
                _cs = getattr(c, "sentiment", "") or ""
                _ct = " [+]" if _cs == "positive" else (" [-]" if _cs == "negative" else (" [~]" if _cs in ("neutral", "constructive") else ""))
                _lines.append(
                    f"  [COMMENT id={c.id}] {c.author_name} (+{c.upvotes}){_ct}\n"
                    f"  {c.content[:150]}"
                )
                replies = children_map.get(c.id, [])
                replies_sorted = sorted(replies, key=lambda p: -p.upvotes)[:2]
                for r in replies_sorted:
                    _reply_ids.append(r.id)
                    _rs = getattr(r, "sentiment", "") or ""
                    _rt = " [+]" if _rs == "positive" else (" [-]" if _rs == "negative" else (" [~]" if _rs in ("neutral", "constructive") else ""))
                    _lines.append(
                        f"    ↳ [REPLY id={r.id}] {r.author_name} (+{r.upvotes}){_rt}\n"
                        f"    ↳ {r.content[:100]}"
                    )
            return "\n".join(_lines), _comment_ids, _reply_ids

        # Pre-render all posts once for O(N) truncation
        rendered_current: list[tuple[SocialPost, str, list[str], list[str]]] = []
        if current_round_posts:
            for post in current_round_posts:
                text, cids, rids = _render_post(post)
                rendered_current.append((post, text, cids, rids))

        rendered_earlier: list[tuple[SocialPost, str, list[str], list[str]]] = []
        if earlier_posts:
            for post in earlier_posts:
                text, cids, rids = _render_post(post)
                rendered_earlier.append((post, text, cids, rids))

        # Build base lines (header + sentiment)
        base_header = "\n".join(lines)

        # Build current round section
        current_section_parts: list[str] = []
        if rendered_current:
            current_section_parts.append("\n[NEW THIS ROUND]")
            for _, text, _, _ in rendered_current:
                current_section_parts.append(text)
        current_section = "\n".join(current_section_parts)

        # Calculate budget for earlier posts
        # Reserve space for the targetable IDs line (estimate)
        ids_line_estimate = 80  # conservative estimate for the IDs footer
        base_len = len(base_header) + len(current_section) + ids_line_estimate
        budget = max_feed_chars - base_len

        # Select earlier posts within budget (priority order: first = highest priority)
        selected_earlier: list[tuple[SocialPost, str, list[str], list[str]]] = []
        used = 0
        if budget > 0 and rendered_earlier:
            # Add section header cost
            earlier_header = "\n[EARLIER]"
            header_cost = len(earlier_header) + 1  # +1 for join newline
            used += header_cost
            for entry in rendered_earlier:
                chunk_len = len(entry[1]) + 1  # +1 for newline
                if used + chunk_len > budget:
                    break
                selected_earlier.append(entry)
                used += chunk_len

        # Assemble final lines and collect IDs
        comment_ids = []
        reply_ids = []
        if rendered_current:
            lines.append("\n[NEW THIS ROUND]")
            for _, text, cids, rids in rendered_current:
                lines.append(text)
                comment_ids.extend(cids)
                reply_ids.extend(rids)

        if selected_earlier:
            lines.append("\n[EARLIER]")
            for _, text, cids, rids in selected_earlier:
                lines.append(text)
                comment_ids.extend(cids)
                reply_ids.extend(rids)

        # Build targetable IDs from selected posts only
        selected_earlier_posts = [entry[0] for entry in selected_earlier]
        top_level_sorted = current_round_posts + selected_earlier_posts
        targetable_ids = [p.id for p in top_level_sorted] + comment_ids + reply_ids
        # In later rounds, move seed post to end of targetable_ids to reduce LLM bias toward it
        if round_num >= 3:
            seed_ids = [p.id for p in state.posts if p.author_node_id == "__seed__"]
            for sid in seed_ids:
                if sid in targetable_ids:
                    targetable_ids = [t for t in targetable_ids if t != sid] + [sid]
        lines.append("\n[Available post/comment IDs for targeting]: " + ", ".join(targetable_ids))

        result = "\n".join(lines)

        return result

    def build_reply_candidates(
        self,
        state: PlatformState,
        persona: "Persona",
        top_n: int = 5,
        interaction_ledger: dict | None = None,
        personas_map: dict | None = None,
        children_map: dict | None = None,
    ) -> str:
        """Return a compact text block of underexplored reply-target candidates.

        Prioritises posts with low reply_count (0-2) that are topically relevant
        to *persona*.  Meant to be appended after the compact feed so the LLM
        is aware of threads that deserve more engagement.

        When interaction_ledger is provided, ongoing-debate counterparts
        (disagreed_count >= 2) are promoted to the top with [ONGOING DEBATE],
        and ally counterparts (agreed_count >= 2) are appended with [ALLY].

        When children_map (parent_id -> list[SocialPost]) is provided, use it
        for O(1) child-count lookups instead of relying solely on the stored
        reply_count attribute.  Falls back to reply_count when children_map is
        None (backward-compatible).
        """
        # 1. Filter to reply-eligible posts (seed / post / comment with content)
        def _effective_reply_count(p: SocialPost) -> int:
            """Return child count from children_map if available, else stored reply_count."""
            if children_map is not None:
                return max(0, len(children_map.get(p.id, [])))
            return max(0, p.reply_count or 0)

        candidates = [
            p for p in state.posts
            if p.author_node_id != persona.node_id
            and _effective_reply_count(p) <= 2
            and p.action_type in ("seed", "post", "comment", "new_post")
            and p.content
        ]
        if not candidates:
            return ""

        # 2. Build persona keyword set from interests + tech_area
        persona_keywords: set[str] = set()
        if persona.interests:
            for kw in persona.interests:
                persona_keywords.update(kw.lower().split())
        if persona.tech_area:
            for kw in persona.tech_area:
                persona_keywords.update(kw.lower().split())

        def _relevance(post: SocialPost) -> int:
            if not persona_keywords:
                return 0
            words = set(post.content.lower().split())
            return len(persona_keywords & words)

        # 3. Sort: relevance + reply scarcity bonus, break ties by fewer replies
        def _sort_key(post: SocialPost) -> tuple:
            rel = _relevance(post)
            rc = _effective_reply_count(post)
            reply_bonus = max(0, 2 - rc)
            return (rel + reply_bonus, -rc)

        candidates.sort(key=_sort_key, reverse=True)
        top_candidates = candidates[:top_n]

        # ── interaction_ledger-based priority injection ──
        debate_lines: list[str] = []  # [ONGOING DEBATE] posts (top, max 2)
        ally_lines: list[str] = []    # [ALLY] posts (bottom, max 1)

        if interaction_ledger:
            # Counterparts with disagreed_count >= 2 -> ongoing debate targets
            debate_nids = [
                nid for nid, entry in interaction_ledger.items()
                if entry.get("disagreed_count", 0) >= 2
            ]
            # Counterparts with agreed_count >= 2 -> ally targets
            ally_nids = [
                nid for nid, entry in interaction_ledger.items()
                if entry.get("agreed_count", 0) >= 2
            ]

            # Build index: author_node_id -> most recent post
            author_latest: dict[str, SocialPost] = {}
            for p in state.posts:
                if p.author_node_id != persona.node_id and p.content:
                    existing = author_latest.get(p.author_node_id)
                    if existing is None or getattr(p, "round_num", 0) > getattr(existing, "round_num", 0):
                        author_latest[p.author_node_id] = p

            for nid in debate_nids[:2]:
                post = author_latest.get(nid)
                if post and post.author_node_id != persona.node_id:
                    snippet = post.content[:80].replace("\n", " ")
                    debate_lines.append(
                        f"[ONGOING DEBATE] [{post.id}] @{post.author_name} "
                        f"({post.sentiment or 'neutral'}, {_effective_reply_count(post)} replies): "
                        f"{snippet}..."
                    )

            for nid in ally_nids[:1]:
                post = author_latest.get(nid)
                if post and post.author_node_id != persona.node_id:
                    snippet = post.content[:80].replace("\n", " ")
                    ally_lines.append(
                        f"[ALLY] [{post.id}] @{post.author_name} "
                        f"({post.sentiment or 'neutral'}, {_effective_reply_count(post)} replies): "
                        f"{snippet}..."
                    )

        # 4. Build post_index for parent lookup (reuse state helper)
        lines = ["[REPLY CANDIDATES - underexplored threads]"]

        # Insert debate targets at the top
        lines.extend(debate_lines)

        # Seniority levels that qualify for [SENIOR PERSPECTIVE] tag
        _SENIOR_LEVELS = ('director', 'vp', 'c_suite')

        for post in top_candidates:
            snippet = post.content[:80].replace("\n", " ")
            parent_context = ""
            if post.parent_id:
                parent = state.get_post(post.parent_id)
                if parent:
                    parent_snippet = parent.content[:40].replace("\n", " ")
                    parent_context = (
                        f' (reply to @{parent.author_name}: "{parent_snippet}")'
                    )
            # Tag senior authors so LLM weighs their perspective higher
            _cand_author = personas_map.get(post.author_node_id) if personas_map else None
            _cand_sen = getattr(_cand_author, 'seniority', '') or ''
            senior_tag = "[SENIOR PERSPECTIVE] " if _cand_sen in _SENIOR_LEVELS else ""
            lines.append(
                f"{senior_tag}[{post.id}] @{post.author_name} "
                f"({post.sentiment or 'neutral'}, {_effective_reply_count(post)} replies): "
                f"{snippet}...{parent_context}"
            )

        # Append ally targets at the bottom
        lines.extend(ally_lines)

        return "\n".join(lines)

    def build_round_topics_hint(
        self,
        state: PlatformState,
        round_num: int,
        max_topics: int = 5,
    ) -> str:
        """Return a compact summary of posts already created in this round.

        Used by callers (e.g. social_rounds.py) to inject as a local-variable
        hint so that subsequent agents avoid duplicating topics.
        Returns an empty string when no posts exist for the given round.
        """
        round_posts = [p for p in state.posts if p.round_num == round_num]
        if not round_posts:
            return ""

        round_posts.sort(key=lambda p: p.weighted_score or 0.0, reverse=True)
        selected = round_posts[:max_topics]

        lines: list[str] = ["[ALREADY DISCUSSED THIS ROUND]"]
        for p in selected:
            sentiment_label = p.sentiment or "neutral"
            snippet = p.content[:40].replace("\n", " ")
            lines.append(
                f"- {sentiment_label}: \"{snippet}...\" (@{p.author_name})"
            )

        result = "\n".join(lines)
        if len(result) > 200:
            result = result[:197] + "..."
        return result

    SENIORITY_WEIGHTS = {
        "intern": 0.5, "junior": 0.7, "mid": 1.0, "senior": 1.3,
        "lead": 1.5, "principal": 1.7, "director": 2.0, "vp": 2.3, "c_suite": 2.5,
    }

    def _apply_vote_common(
        self,
        state: PlatformState,
        target_post_id: str,
        action_type: str,
        round_num: int,
        voter_node_id: str,
        seniority: str = "",
    ) -> tuple[SocialPost | None, bool]:
        """공통 투표 로직을 수행하고 (post, is_duplicate) 를 반환한다.

        is_duplicate=True이면 중복 투표이므로 호출부에서 early return 처리.
        처리 내용: voter dedup, vote_rounds.append, voters.append, endorsed_by 기록.
        """
        post = state.get_post(target_post_id)
        if post is None:
            return None, True
        # Prevent duplicate votes from the same agent
        if voter_node_id and voter_node_id in post.voters:
            return post, True
        post.vote_rounds.append(round_num)
        if voter_node_id:
            post.voters.append(voter_node_id)
            # Record senior endorsement for upvote/react/like actions
            if action_type in ("upvote", "react", "like") and seniority.lower() in _SENIOR_ENDORSERS:
                if voter_node_id not in post.endorsed_by:
                    post.endorsed_by.append(voter_node_id)
        return post, False

    def _seniority_weight(self, seniority: str) -> float:
        """Resolve seniority string to a numeric weight."""
        for key, val in self.SENIORITY_WEIGHTS.items():
            if key in seniority.lower():
                return val
        return 1.0

    def update_vote_counts(
        self,
        state: PlatformState,
        target_post_id: str,
        action_type: str,
        round_num: int = 0,
        voter_node_id: str = "",
        seniority: str = "",
        **kwargs,
    ) -> SocialPost | None:
        """Mutate upvote/downvote count on target post. Returns updated post or None."""
        post, is_duplicate = self._apply_vote_common(
            state, target_post_id, action_type, round_num, voter_node_id, seniority,
        )
        if is_duplicate or post is None:
            return post
        weight = self._seniority_weight(seniority)
        if action_type in ("upvote", "react", "like"):
            post.upvotes += 1
            post.weighted_score += weight
        elif action_type in ("downvote", "flag"):
            post.downvotes += 1
            post.weighted_score = max(0.0, post.weighted_score - weight * 0.5)
        return post
