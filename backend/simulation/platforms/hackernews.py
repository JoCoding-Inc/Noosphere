from backend.simulation.platforms.base import AbstractPlatform
from backend.simulation.models import SocialPost, PlatformState


class HackerNews(AbstractPlatform):
    name = "hackernews"
    allowed_actions = ["comment", "reply", "upvote", "flag", "ask_hn", "new_post"]
    no_content_actions = {"upvote", "flag"}
    _flag_penalty = 2  # flags carry stronger downvote penalty than regular downvotes
    seed_controversy_hint = "Include a debatable technical claim or tradeoff that experienced engineers might challenge."
    system_prompt = (
        "You are a Hacker News user. Be technical, concise, and intellectually rigorous. "
        "Prefer short, substantive comments. Ask clarifying questions. "
        "Skepticism is the default. Avoid hype. Flag irrelevant posts."
    )

    def content_tool(self, action_type: str) -> dict:
        if action_type == "new_post":
            return {
                "name": "create_content",
                "description": "Submit a new Hacker News post.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "title": {
                            "type": "string",
                            "description": "HN post title — factual, no hype, under 80 chars.",
                        },
                        "text": {
                            "type": "string",
                            "description": "Body text for the post. Can be empty for link submissions.",
                        },
                        "sentiment": {
                            "type": "string",
                            "enum": ["positive", "neutral", "negative", "constructive"],
                            "description": "Overall sentiment of this content toward the idea/product",
                        },
                    },
                    "required": ["title", "text", "sentiment"],
                },
            }
        if action_type == "ask_hn":
            return {
                "name": "create_content",
                "description": "Write an Ask HN post. Pose a thoughtful question to the community.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "text": {
                            "type": "string",
                            "description": "Body text providing context for the question. 2-5 sentences.",
                        },
                        "question": {
                            "type": "string",
                            "description": "The core question to ask the HN community.",
                        },
                        "sentiment": {
                            "type": "string",
                            "enum": ["positive", "neutral", "negative", "constructive"],
                            "description": "Overall sentiment of this content toward the idea/product",
                        },
                    },
                    "required": ["text", "question", "sentiment"],
                },
            }
        return {
            "name": "create_content",
            "description": f"Write a {action_type} on Hacker News. Be concise and technical.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "Comment or reply text. 1-4 sentences, technical and direct.",
                    },
                    "is_question": {
                        "type": "boolean",
                        "description": "True if this comment primarily asks a clarifying question.",
                    },
                    "sentiment": {
                        "type": "string",
                        "enum": ["positive", "neutral", "negative", "constructive"],
                        "description": "Overall sentiment of this content toward the idea/product",
                    },
                },
                "required": ["text", "is_question", "sentiment"],
            },
        }

    def seed_tool(self) -> dict:
        return {
            "name": "create_seed_post",
            "description": "Write a Hacker News submission introducing an idea.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "HN submission title — factual, no hype, under 80 chars.",
                    },
                    "url": {
                        "type": ["string", "null"],
                        "description": "Optional URL for link submissions, or null for text-only posts.",
                    },
                    "text": {
                        "type": "string",
                        "description": "Optional body text (Ask HN / Show HN style). Can be empty for link submissions.",
                    },
                },
                "required": ["title", "text"],
            },
        }

    def extract_content(self, action_type: str, structured_data: dict) -> str:
        if action_type == "new_post":
            return f"**{structured_data.get('title', '')}**\n\n{structured_data.get('text', '')}".strip()
        if action_type == "ask_hn":
            question = structured_data.get("question", "")
            text = structured_data.get("text", "")
            return f"Ask HN: {question}\n{text}".strip()
        return structured_data.get("text", "")

    def extract_seed_content(self, structured_data: dict) -> str:
        title = structured_data.get("title", "")
        text = structured_data.get("text", "")
        return f"{title}\n{text}".strip() if text else title

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
        """Override: flags carry a stronger downvote penalty (_flag_penalty=2)."""
        post, is_duplicate = self._apply_vote_common(
            state, target_post_id, action_type, round_num, voter_node_id, seniority,
        )
        if is_duplicate or post is None:
            return post
        weight = self._seniority_weight(seniority)
        if action_type in ("upvote",):
            post.upvotes += 1
            post.weighted_score += weight
        elif action_type == "flag":
            post.downvotes += self._flag_penalty
            post.weighted_score = max(0.0, post.weighted_score - weight * 0.5 * self._flag_penalty)
        elif action_type == "downvote":
            post.downvotes += 1
            post.weighted_score = max(0.0, post.weighted_score - weight * 0.5)
        return post
