from __future__ import annotations
import random
from typing import TYPE_CHECKING

from backend.simulation.platforms.base import AbstractPlatform
from backend.simulation.models import SocialPost, PlatformState

if TYPE_CHECKING:
    from backend.simulation.models import Persona


class LinkedIn(AbstractPlatform):
    name = "linkedin"
    allowed_actions = ["comment", "reply", "react", "share", "article"]
    no_content_actions = {"react"}
    seed_controversy_hint = "Make a contrarian industry take related to the problem being solved."
    system_prompt = (
        "You are a LinkedIn professional — executive, investor, or domain expert. "
        "Write in a professional, structured tone. "
        "Comments should offer business insight or strategic perspective. "
        "Shares should add your own framing. React with Like or Insightful."
    )

    def content_tool(self, action_type: str) -> dict:
        if action_type == "reply":
            return {
                "name": "create_content",
                "description": "Write a LinkedIn reply to another comment. Professional and insightful.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "text": {
                            "type": "string",
                            "description": "Reply text. Professional tone, 1-3 sentences. Address the parent comment directly.",
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
        if action_type == "article":
            return {
                "name": "create_content",
                "description": "Write a LinkedIn article with a professional, long-form perspective.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "title": {
                            "type": "string",
                            "description": "Article title — clear and professional.",
                        },
                        "text": {
                            "type": "string",
                            "description": "Article body. Professional tone, 4-8 sentences with structured reasoning.",
                        },
                        "key_takeaway": {
                            "type": "string",
                            "description": "The single most important takeaway for the reader.",
                        },
                        "sentiment": {
                            "type": "string",
                            "enum": ["positive", "neutral", "negative", "constructive"],
                            "description": "Tone toward the idea — positive: genuinely excited or fully supportive with ZERO reservations (use ONLY if you have no doubts); neutral: mixed, exploratory, or mildly interested; negative: any doubt, concern, criticism, or skepticism — DEFAULT for critical posts; constructive: ONLY if the entire response is an explicit numbered improvement list (extremely rare, <5%)",
                        },
                    },
                    "required": ["title", "text", "key_takeaway", "sentiment"],
                },
            }
        if action_type == "share":
            return {
                "name": "create_content",
                "description": "Write a LinkedIn share post adding your professional perspective.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "text": {
                            "type": "string",
                            "description": "Main post body. Professional tone, 2-4 sentences.",
                        },
                        "business_insight": {
                            "type": "string",
                            "description": "A specific business or market insight this idea illustrates.",
                        },
                        "hashtags": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "2-4 relevant professional hashtags (without # symbol).",
                            "minItems": 2,
                            "maxItems": 4,
                        },
                        "sentiment": {
                            "type": "string",
                            "enum": ["positive", "neutral", "negative", "constructive"],
                            "description": "Tone toward the idea — positive: genuinely excited or fully supportive with ZERO reservations (use ONLY if you have no doubts); neutral: mixed, exploratory, or mildly interested; negative: any doubt, concern, criticism, or skepticism — DEFAULT for critical posts; constructive: ONLY if the entire response is an explicit numbered improvement list (extremely rare, <5%)",
                        },
                    },
                    "required": ["text", "business_insight", "hashtags", "sentiment"],
                },
            }
        # comment
        return {
            "name": "create_content",
            "description": "Write a LinkedIn comment offering professional perspective.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "Professional comment with business or strategic insight. 2-3 sentences.",
                    },
                    "stance": {
                        "type": "string",
                        "enum": ["supportive", "critical", "neutral"],
                        "description": "Overall stance toward the idea.",
                    },
                    "sentiment": {
                        "type": "string",
                        "enum": ["positive", "neutral", "negative", "constructive"],
                        "description": "Tone toward the idea — positive: genuinely excited or fully supportive with ZERO reservations (use ONLY if you have no doubts); neutral: mixed, exploratory, or mildly interested; negative: any doubt, concern, criticism, or skepticism — DEFAULT for critical posts; constructive: ONLY if the entire response is an explicit numbered improvement list (extremely rare, <5%)",
                    },
                },
                "required": ["text", "stance", "sentiment"],
            },
        }

    def seed_tool(self) -> dict:
        return {
            "name": "create_seed_post",
            "description": "Write a LinkedIn post introducing a product idea to a professional audience.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "headline": {
                        "type": "string",
                        "description": "Attention-grabbing headline or opening line. 1 sentence.",
                    },
                    "body": {
                        "type": "string",
                        "description": "Main content covering the problem, solution, and market opportunity. 3-5 sentences.",
                    },
                    "hashtags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "2-5 relevant professional hashtags (without # symbol).",
                        "minItems": 2,
                        "maxItems": 5,
                    },
                },
                "required": ["headline", "body", "hashtags"],
            },
        }

    def extract_content(self, action_type: str, structured_data: dict) -> str:
        text = structured_data.get("text", "")
        if action_type == "article":
            title = structured_data.get("title", "")
            key_takeaway = structured_data.get("key_takeaway", "")
            parts = [p for p in [title, text, f"Key takeaway: {key_takeaway}" if key_takeaway else ""] if p]
            return "\n".join(parts)
        if action_type == "reply":
            return text
        if action_type == "share":
            insight = structured_data.get("business_insight", "")
            hashtags = structured_data.get("hashtags", [])
            parts = [text]
            if insight:
                parts.append(f"\n{insight}")
            if hashtags:
                parts.append("\n" + " ".join(f"#{tag}" for tag in hashtags))
            return "\n".join(parts)
        return text

    def extract_seed_content(self, structured_data: dict) -> str:
        headline = structured_data.get("headline", "") or structured_data.get("hook", "")
        body = structured_data.get("body", "")
        hashtags = structured_data.get("hashtags", [])
        hashtags_str = " ".join(f"#{tag}" for tag in hashtags) if hashtags else ""
        parts = [headline, body]
        if hashtags_str:
            parts.append(hashtags_str)
        return "\n".join(p for p in parts if p)

    # Seniority levels allowed to publish long-form articles
    _ARTICLE_SENIORITY = {"director", "vp", "c_suite", "principal", "lead"}

    def get_allowed_actions(self, persona: "Persona") -> list[str]:
        """Override: restrict 'article' action to senior-level personas only."""
        actions = list(self.allowed_actions)
        if persona.seniority.lower() not in self._ARTICLE_SENIORITY:
            actions = [a for a in actions if a != "article"]
        return actions

    # Senior roles are more likely to give "insightful" reactions on LinkedIn
    _INSIGHTFUL_SENIORITY = {"senior", "lead", "principal", "director", "vp", "c_suite"}

    def update_vote_counts(
        self,
        state: PlatformState,
        target_post_id: str,
        action_type: str,
        round_num: int = 0,
        voter_node_id: str = "",
        seniority: str = "",
        personas_map: dict | None = None,
        **kwargs,
    ) -> SocialPost | None:
        """Override: LinkedIn 'react' actions differentiate by react_type.

        Senior professionals are more likely to give 'insightful' reactions,
        which carry a +2 upvote weight instead of +1.
        Domain experts reacting to same-domain posts also get a boost.
        """
        post, is_duplicate = self._apply_vote_common(
            state, target_post_id, action_type, round_num, voter_node_id, seniority,
        )
        if is_duplicate or post is None:
            return post
        weight = self._seniority_weight(seniority)
        if action_type == "react":
            # Determine react_type heuristically: senior roles -> higher chance of "insightful"
            is_senior = any(s in seniority.lower() for s in self._INSIGHTFUL_SENIORITY)
            insightful_prob = 0.5 if is_senior else 0.2
            # Domain expertise match: voter and post author share the same domain_type
            if personas_map and voter_node_id and post.author_node_id:
                voter_persona = personas_map.get(voter_node_id)
                author_persona = personas_map.get(post.author_node_id)
                if (voter_persona and author_persona
                        and getattr(voter_persona, "domain_type", "")
                        and voter_persona.domain_type == author_persona.domain_type):
                    insightful_prob = min(0.75, insightful_prob + 0.25)
            react_type = "insightful" if random.random() < insightful_prob else "like"
            if react_type == "insightful":
                post.upvotes += 2
                post.weighted_score += weight * 2
            else:
                post.upvotes += 1
                post.weighted_score += weight
        elif action_type in ("upvote", "like"):
            post.upvotes += 1
            post.weighted_score += weight
        elif action_type in ("downvote", "flag"):
            post.downvotes += 1
            post.weighted_score = max(0.0, post.weighted_score - weight * 0.5)
        return post
