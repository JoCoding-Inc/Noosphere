from __future__ import annotations
from typing import TYPE_CHECKING
from backend.simulation.platforms.base import AbstractPlatform

if TYPE_CHECKING:
    from backend.simulation.models import Persona


class ProductHunt(AbstractPlatform):
    name = "producthunt"
    allowed_actions = ["review", "ask_question", "maker_response", "upvote"]
    no_content_actions = {"upvote"}
    system_prompt = (
        "You are a Product Hunt user or maker. Be enthusiastic but specific. "
        "Reviews should cover use case, UX, and differentiation. "
        "Questions should be genuine curiosity about the product. "
        "Makers defend their product professionally and honestly."
    )

    def get_allowed_actions(self, persona: "Persona") -> list[str]:
        # maker_response only available to commercially-driven personas (commercial_focus >= 7)
        if persona.commercial_focus >= 7:
            return list(self.allowed_actions)
        return [a for a in self.allowed_actions if a != "maker_response"]

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
                    },
                    "required": ["text", "rating", "pros", "cons"],
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
                    },
                    "required": ["text"],
                },
            }
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
                    },
                    "required": ["text", "addresses_concern"],
                },
            }
        # fallback
        return super().content_tool(action_type)

    def seed_tool(self) -> dict:
        return {
            "name": "create_seed_post",
            "description": "Write a Product Hunt launch post for this product.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "tagline": {
                        "type": "string",
                        "description": "Catchy one-line tagline under 60 chars.",
                    },
                    "description": {
                        "type": "string",
                        "description": "Product description covering what it does, who it's for, and why it's different. 2-3 sentences.",
                    },
                    "makers_comment": {
                        "type": "string",
                        "description": "Personal note from the maker sharing the story behind the product.",
                    },
                },
                "required": ["tagline", "description", "makers_comment"],
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
        tagline = structured_data.get("tagline", "")
        description = structured_data.get("description", "")
        makers_comment = structured_data.get("makers_comment", "")
        parts = [p for p in [tagline, description, makers_comment] if p]
        return "\n\n".join(parts)
