from __future__ import annotations
from typing import TYPE_CHECKING

from backend.simulation.platforms.base import AbstractPlatform

if TYPE_CHECKING:
    from backend.simulation.models import Persona


class IndieHackers(AbstractPlatform):
    name = "indiehackers"
    allowed_actions = ["comment", "reply", "share_experience", "ask_advice", "milestone", "upvote"]
    no_content_actions: set = {"upvote"}
    seed_controversy_hint = (
        "Share a specific metric or number that some may find unrealistic. "
        "End with a pointed question that invites founders to share their own contrasting experience."
    )

    # Seniority levels allowed to post milestones (in addition to founder-segment personas)
    _MILESTONE_SENIORITY = {"c_suite", "vp", "director"}

    def get_allowed_actions(self, persona: "Persona") -> list[str]:
        """Override: restrict 'milestone' to founders and senior leadership."""
        actions = list(self.allowed_actions)
        seniority_ok = persona.seniority.lower() in self._MILESTONE_SENIORITY
        # Founder segment: role contains "founder" or affiliation is "startup"
        founder_ok = "founder" in persona.role.lower() or persona.affiliation.lower() == "startup"
        if not (seniority_ok or founder_ok):
            actions = [a for a in actions if a != "milestone"]
        return actions

    system_prompt = (
        "You are an IndieHackers member — a bootstrapper or solo founder. "
        "Focus on revenue, retention, and real-world execution. "
        "Share personal experience. Ask about monetization and growth. "
        "Be supportive but honest about risks."
    )

    def content_tool(self, action_type: str) -> dict:
        if action_type == "reply":
            return {
                "name": "create_content",
                "description": "Reply directly to another founder's comment or question on IndieHackers",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "text": {
                            "type": "string",
                            "description": "Your reply (conversational, founder-to-founder tone, 2-4 sentences)",
                        },
                        "sentiment": {
                            "type": "string",
                            "enum": ["positive", "neutral", "negative", "constructive"],
                            "description": "Overall sentiment of this content toward the idea/product",
                        },
                    },
                    "required": ["text", "sentiment"],
                },
            }
        if action_type == "share_experience":
            return {
                "name": "create_content",
                "description": "Share a personal experience or lesson on Indie Hackers.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "text": {
                            "type": "string",
                            "description": "Personal experience or reflection. 2-4 sentences, first-person, specific.",
                        },
                        "mrr_context": {
                            "type": ["string", "null"],
                            "description": "MRR or revenue figure if relevant (e.g. '$2k MRR after 6 months'), or null.",
                        },
                        "lesson": {
                            "type": "string",
                            "description": "The key takeaway or lesson from your experience.",
                        },
                        "sentiment": {
                            "type": "string",
                            "enum": ["positive", "neutral", "negative", "constructive"],
                            "description": "Overall sentiment of this content toward the idea/product",
                        },
                    },
                    "required": ["text", "mrr_context", "lesson", "sentiment"],
                },
            }
        if action_type == "milestone":
            return {
                "name": "create_content",
                "description": "Share a milestone achievement on Indie Hackers.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "text": {
                            "type": "string",
                            "description": "Description of the milestone. 2-4 sentences, first-person.",
                        },
                        "milestone_type": {
                            "type": "string",
                            "enum": ["first_customer", "revenue", "launch", "pivot"],
                            "description": "Type of milestone achieved.",
                        },
                        "metric": {
                            "type": ["string", "null"],
                            "description": "Quantitative metric if applicable (e.g. '$1k MRR', '100 users'), or null.",
                        },
                        "sentiment": {
                            "type": "string",
                            "enum": ["positive", "neutral", "negative", "constructive"],
                            "description": "Overall sentiment of this content toward the idea/product",
                        },
                    },
                    "required": ["text", "milestone_type", "metric", "sentiment"],
                },
            }
        if action_type == "ask_advice":
            return {
                "name": "create_content",
                "description": "Ask for advice from the Indie Hackers community.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "text": {
                            "type": "string",
                            "description": "Context and framing for your question. 1-3 sentences.",
                        },
                        "specific_question": {
                            "type": "string",
                            "description": "The focused, actionable question you need answered.",
                        },
                        "sentiment": {
                            "type": "string",
                            "enum": ["positive", "neutral", "negative", "constructive"],
                            "description": "Overall sentiment of this content toward the idea/product",
                        },
                    },
                    "required": ["text", "specific_question", "sentiment"],
                },
            }
        # comment
        return {
            "name": "create_content",
            "description": "Write a comment on Indie Hackers.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "Supportive, honest comment. 1-3 sentences.",
                    },
                    "sentiment": {
                        "type": "string",
                        "enum": ["positive", "neutral", "negative", "constructive"],
                        "description": "Overall sentiment of this content toward the idea/product",
                    },
                },
                "required": ["text", "sentiment"],
            },
        }

    def seed_tool(self) -> dict:
        return {
            "name": "create_seed_post",
            "description": "Write an Indie Hackers post introducing a product idea as a milestone update.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "milestone": {
                        "type": "string",
                        "description": "Milestone headline — clear, specific, outcome-oriented (e.g. 'Just launched X to solve Y').",
                    },
                    "body": {
                        "type": "string",
                        "description": "Post body covering the problem, solution, and current stage. 3-5 sentences.",
                    },
                    "metrics": {
                        "type": ["string", "null"],
                        "description": "Optional quantitative metrics (e.g. '$500 MRR', '200 signups in first week'), or null.",
                    },
                    "discussion_prompt": {
                        "type": "string",
                        "description": "A specific question to the IH community inviting feedback or advice (1 sentence, e.g. 'What pricing strategy would you try first?').",
                    },
                },
                "required": ["milestone", "body", "discussion_prompt"],
            },
        }

    def extract_content(self, action_type: str, structured_data: dict) -> str:
        text = structured_data.get("text", "")
        if action_type == "milestone":
            milestone_type = structured_data.get("milestone_type", "milestone")
            return f"Milestone ({milestone_type}): {text}"
        if action_type == "share_experience":
            lesson = structured_data.get("lesson", "")
            mrr = structured_data.get("mrr_context")
            parts = [text]
            if mrr:
                parts.append(f"[{mrr}]")
            if lesson:
                parts.append(f"Lesson: {lesson}")
            return "\n".join(parts)
        if action_type == "ask_advice":
            question = structured_data.get("specific_question", "")
            return f"{text}\n\n{question}".strip() if question else text
        return text

    def extract_seed_content(self, structured_data: dict) -> str:
        milestone = structured_data.get("milestone", "") or structured_data.get("title", "")
        body = structured_data.get("body", "")
        metrics = structured_data.get("metrics", "") or structured_data.get("stage", "")
        parts = [f"Milestone: {milestone}" if milestone else ""]
        if body:
            parts.append(body)
        if metrics:
            parts.append(f"Metrics: {metrics}")
        discussion = structured_data.get("discussion_prompt", "").strip()
        if discussion:
            parts.append(f"\n{discussion}")
        return "\n".join(p for p in parts if p)
