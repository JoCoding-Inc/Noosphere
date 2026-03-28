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


class AbstractPlatform:
    name: str
    allowed_actions: list[str]
    no_content_actions: set[str]
    system_prompt: str           # Platform persona for LLM

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
                        "enum": ["positive", "neutral", "negative"],
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
        top_posts: int = 3,
        top_comments_per_post: int = 2,
    ) -> str:
        """Render platform feed as text for LLM context."""
        top_level = [p for p in state.posts if p.parent_id is None]
        top_level_sorted = sorted(top_level, key=lambda p: -p.upvotes)[:top_posts]

        lines: list[str] = [f"=== {self.name.upper()} FEED (Round {state.round_num}) ==="]
        for post in top_level_sorted:
            lines.append(
                f"\n[POST id={post.id}] {post.author_name} (+{post.upvotes}/-{post.downvotes})\n"
                f"{post.content[:300]}"
            )
            comments = [p for p in state.posts if p.parent_id == post.id]
            comments_sorted = sorted(comments, key=lambda p: -p.upvotes)[:top_comments_per_post]
            for c in comments_sorted:
                lines.append(
                    f"  [COMMENT id={c.id}] {c.author_name} (+{c.upvotes})\n"
                    f"  {c.content[:150]}"
                )
        # Include comment IDs so agents can reply to specific comments
        comment_ids = [
            c.id
            for post in top_level_sorted
            for c in sorted(
                [p for p in state.posts if p.parent_id == post.id],
                key=lambda p: -p.upvotes,
            )[:top_comments_per_post]
        ]
        targetable_ids = [p.id for p in top_level_sorted] + comment_ids
        lines.append("\n[Available post/comment IDs for targeting]: " + ", ".join(targetable_ids))
        return "\n".join(lines)

    def update_vote_counts(
        self,
        state: PlatformState,
        target_post_id: str,
        action_type: str,
    ) -> SocialPost | None:
        """Mutate upvote/downvote count on target post. Returns updated post or None."""
        post = state.get_post(target_post_id)
        if post is not None:
            if action_type in ("upvote", "react"):
                post.upvotes += 1
            elif action_type in ("downvote", "flag"):
                post.downvotes += 1
        return post
