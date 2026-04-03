from __future__ import annotations
from typing import TYPE_CHECKING
from backend.simulation.platforms.base import AbstractPlatform

if TYPE_CHECKING:
    from backend.simulation.models import Persona, PlatformState, SocialPost


class ProductHunt(AbstractPlatform):
    name = "producthunt"
    allowed_actions = ["review", "ask_question", "comment", "reply", "upvote"]
    no_content_actions = {"upvote"}
    seed_controversy_hint = "Include a bold pricing or positioning statement that may polarize the maker community."
    system_prompt = (
        "You are a Product Hunt user or maker. Be enthusiastic but specific. "
        "Reviews should cover use case, UX, and differentiation. "
        "Questions should be genuine curiosity about the product. "
        "Makers defend their product professionally and honestly."
    )

    def get_allowed_actions(self, persona: "Persona") -> list[str]:
        return list(self.allowed_actions)

    def content_tool(self, action_type: str) -> dict:
        if action_type == "review":
            return {
                "name": "create_content",
                "description": "Write a Product Hunt review for this product.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "text": {
                            "type": "string",
                            "description": "Review body — cover use case, experience, and differentiation. 2-4 sentences.",
                        },
                        "rating": {
                            "type": "integer",
                            "description": "Star rating from 1 (poor) to 5 (excellent).",
                            "minimum": 1,
                            "maximum": 5,
                        },
                        "pros": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "1-3 specific strengths of this product.",
                            "minItems": 1,
                            "maxItems": 3,
                        },
                        "cons": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "1-3 specific weaknesses or concerns.",
                            "minItems": 1,
                            "maxItems": 3,
                        },
                        "sentiment": {
                            "type": "string",
                            "enum": ["positive", "neutral", "negative", "constructive"],
                            "description": "Tone toward the idea — positive: genuinely excited or fully supportive with ZERO reservations (use ONLY if you have no doubts); neutral: mixed, exploratory, or mildly interested; negative: any doubt, concern, criticism, or skepticism — DEFAULT for critical posts; constructive: ONLY if the entire response is an explicit numbered improvement list (extremely rare, <5%)",
                        },
                    },
                    "required": ["text", "rating", "pros", "cons", "sentiment"],
                },
            }
        if action_type == "ask_question":
            return {
                "name": "create_content",
                "description": "Write a question for the Product Hunt listing.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "text": {
                            "type": "string",
                            "description": "A genuine, specific question about the product.",
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
        if action_type == "comment":
            return {
                "name": "create_content",
                "description": "Write a comment on a Product Hunt listing.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "text": {
                            "type": "string",
                            "description": "A comment about the product — share your thoughts, feedback, or experience. 1-3 sentences.",
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
        if action_type == "reply":
            return {
                "name": "create_content",
                "description": "Write a direct reply to a comment or question on ProductHunt",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "text": {
                            "type": "string",
                            "description": "Your reply (2-3 sentences, PH-style encouraging tone)",
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
        # Backward compatibility: keep maker_response case for checkpoint restoration
        if action_type == "maker_response":
            return {
                "name": "create_content",
                "description": "Write a maker response on Product Hunt.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "text": {
                            "type": "string",
                            "description": "Professional, honest maker response to a comment or question.",
                        },
                        "addresses_concern": {
                            "type": "string",
                            "description": "The specific concern or question this response is addressing.",
                        },
                        "sentiment": {
                            "type": "string",
                            "enum": ["positive", "neutral", "negative", "constructive"],
                            "description": "Tone toward the idea — positive: genuinely excited or fully supportive with ZERO reservations (use ONLY if you have no doubts); neutral: mixed, exploratory, or mildly interested; negative: any doubt, concern, criticism, or skepticism — DEFAULT for critical posts; constructive: ONLY if the entire response is an explicit numbered improvement list (extremely rare, <5%)",
                        },
                    },
                    "required": ["text", "addresses_concern", "sentiment"],
                },
            }
        # fallback
        return super().content_tool(action_type)

    def update_vote_counts(
        self,
        state: "PlatformState",
        target_post_id: str,
        action_type: str,
        round_num: int = 0,
        voter_node_id: str = "",
        seniority: str = "",
        **kwargs,
    ) -> "SocialPost | None":
        """Override: rating-aware upvote scoring for ProductHunt.

        High-rated reviews (>=4.0) get a weighted_score bonus on upvote,
        while low-rated reviews (<=2.0) get a penalty to suppress spread.
        """
        post = super().update_vote_counts(
            state, target_post_id, action_type, round_num, voter_node_id, seniority
        )
        if post is not None and action_type == "upvote":
            rating = None
            if post.structured_data:
                rating = post.structured_data.get("rating")
            if rating is not None:
                try:
                    r = float(rating)
                    if r >= 4.0:
                        post.weighted_score += 0.5
                    elif r <= 2.0:
                        post.weighted_score = max(0.0, post.weighted_score - 0.3)
                except (ValueError, TypeError):
                    pass
        return post

    def seed_tool(self) -> dict:
        return {
            "name": "create_seed_post",
            "description": "Write a Product Hunt launch post for this product.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "product_name": {
                        "type": "string",
                        "description": "Product name — clear, memorable, under 30 chars.",
                    },
                    "tagline": {
                        "type": "string",
                        "description": "Catchy one-line tagline under 60 chars.",
                    },
                    "description": {
                        "type": "string",
                        "description": "Product description covering what it does, who it's for, and why it's different. 2-3 sentences.",
                    },
                    "maker_comment": {
                        "type": "string",
                        "description": "Personal note from the maker sharing the story behind the product.",
                    },
                },
                "required": ["product_name", "tagline", "description", "maker_comment"],
            },
        }

    def extract_content(self, action_type: str, structured_data: dict) -> str:
        text = structured_data.get("text", "")
        if action_type == "review":
            rating = structured_data.get("rating", "?")
            pros = structured_data.get("pros", [])
            cons = structured_data.get("cons", [])
            pros_str = " | ".join(pros) if pros else ""
            cons_str = " | ".join(cons) if cons else ""
            parts = [f"★{rating}/5  {text}"]
            if pros_str:
                parts.append(f"👍 {pros_str}")
            if cons_str:
                parts.append(f"👎 {cons_str}")
            return "\n".join(parts)
        return text

    def extract_seed_content(self, structured_data: dict) -> str:
        product_name = structured_data.get("product_name", "")
        tagline = structured_data.get("tagline", "")
        description = structured_data.get("description", "")
        # Support both old ("makers_comment") and new ("maker_comment") field names
        maker_comment = structured_data.get("maker_comment", "") or structured_data.get("makers_comment", "")
        headline = f"{product_name} \u2013 {tagline}" if product_name and tagline else (product_name or tagline)
        parts = [headline, description]
        if maker_comment:
            parts.append(f"Maker: {maker_comment}")
        return "\n".join(p for p in parts if p)
