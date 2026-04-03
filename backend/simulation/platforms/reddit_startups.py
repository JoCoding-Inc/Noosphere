from backend.simulation.platforms.base import AbstractPlatform
from backend.simulation.models import SocialPost, PlatformState


class RedditStartups(AbstractPlatform):
    name = "reddit_startups"
    allowed_actions = ["comment", "reply", "upvote", "downvote"]
    no_content_actions = {"upvote", "downvote"}
    seed_controversy_hint = "End with an open question inviting dissenting views from skeptical founders."
    system_prompt = (
        "You are a Reddit r/startups member. Be direct and sometimes skeptical. "
        "Challenge assumptions. Mention competitor products if relevant. "
        "Upvote insightful posts; downvote spam or unoriginal ideas. "
        "Comments should be conversational, not corporate."
    )

    def content_tool(self, action_type: str) -> dict:
        if action_type == "new_post":
            return {
                "name": "create_content",
                "description": "Submit a new Reddit r/startups post.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "title": {
                            "type": "string",
                            "description": "Reddit post title — conversational, honest, under 100 chars.",
                        },
                        "text": {
                            "type": "string",
                            "description": "Post body with context and discussion points. 2-5 sentences.",
                        },
                        "flair": {
                            "type": ["string", "null"],
                            "description": "Optional flair tag for the post (e.g. 'Feedback', 'Discussion').",
                        },
                        "sentiment": {
                            "type": "string",
                            "enum": ["positive", "neutral", "negative", "constructive"],
                            "description": "Tone toward the idea — positive: genuinely excited or fully supportive with ZERO reservations (use ONLY if you have no doubts); neutral: mixed, exploratory, or mildly interested; negative: any doubt, concern, criticism, or skepticism — DEFAULT for critical posts; constructive: ONLY if the entire response is an explicit numbered improvement list (extremely rare, <5%)",
                        },
                    },
                    "required": ["title", "text", "sentiment"],
                },
            }
        if action_type == "reply":
            return {
                "name": "create_content",
                "description": "Write a Reddit r/startups reply to another comment. Be direct and conversational.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "text": {
                            "type": "string",
                            "description": "Reply text. Direct, conversational, 1-3 sentences. Address the parent comment.",
                        },
                        "sentiment": {
                            "type": "string",
                            "enum": ["positive", "neutral", "negative", "constructive"],
                            "description": "Tone toward the idea — positive: genuinely excited or fully supportive with ZERO reservations (use ONLY if you have no doubts); neutral: mixed, exploratory, or mildly interested; negative: any doubt, concern, criticism, or skepticism — DEFAULT for critical posts; constructive: ONLY if the entire response is an explicit numbered improvement list (extremely rare, <5%)",
                        },
                    },
                    "required": ["text", "sentiment"],
                },
            }
        return {
            "name": "create_content",
            "description": "Write a Reddit r/startups comment.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "Conversational comment. Direct, honest, 1-4 sentences. May challenge assumptions.",
                    },
                    "contrarian_point": {
                        "type": ["string", "null"],
                        "description": "A specific counterargument or alternative perspective, or null if generally agreeable.",
                    },
                    "sentiment": {
                        "type": "string",
                        "enum": ["positive", "neutral", "negative", "constructive"],
                        "description": "Tone toward the idea — positive: genuinely excited or fully supportive with ZERO reservations (use ONLY if you have no doubts); neutral: mixed, exploratory, or mildly interested; negative: any doubt, concern, criticism, or skepticism — DEFAULT for critical posts; constructive: ONLY if the entire response is an explicit numbered improvement list (extremely rare, <5%)",
                    },
                },
                "required": ["text", "contrarian_point", "sentiment"],
            },
        }

    def seed_tool(self) -> dict:
        return {
            "name": "create_seed_post",
            "description": "Write a Reddit r/startups post introducing an idea.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Post title — conversational, honest, under 100 chars. No hype.",
                    },
                    "body": {
                        "type": "string",
                        "description": "Post body with context, the problem being solved, and an invitation for feedback. 3-5 sentences.",
                    },
                },
                "required": ["title", "body"],
            },
        }

    def extract_content(self, action_type: str, structured_data: dict) -> str:
        if action_type == "new_post":
            return f"**{structured_data.get('title', '')}**\n\n{structured_data.get('text', '')}".strip()
        text = structured_data.get("text", "")
        if action_type == "reply":
            return text
        contrarian = structured_data.get("contrarian_point")
        if contrarian:
            return f"{text}\n\nCounter-point: {contrarian}"
        return text

    def extract_seed_content(self, structured_data: dict) -> str:
        title = structured_data.get("title", "")
        body = structured_data.get("body", "")
        return f"{title}\n{body}".strip() if body else title

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
        """Override: Reddit vote scores decay over time.

        Older posts receive less weighted_score boost from new votes,
        reflecting Reddit's time-based ranking algorithm.
        decay_factor = max(0.5, 1.0 - (current_round - post.round_num) * 0.1)
        """
        post, is_duplicate = self._apply_vote_common(
            state, target_post_id, action_type, round_num, voter_node_id, seniority,
        )
        if is_duplicate or post is None:
            return post
        weight = self._seniority_weight(seniority)
        # Time decay: older posts get less weighted_score from votes
        decay_factor = max(0.5, min(1.0, 1.0 - (round_num - post.round_num) * 0.1))
        if action_type in ("upvote", "react", "like"):
            post.upvotes += 1
            post.weighted_score += decay_factor * weight
        elif action_type in ("downvote", "flag"):
            post.downvotes += 1
            post.weighted_score = max(0.0, post.weighted_score - decay_factor * weight * 0.5)
        return post
