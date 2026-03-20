from backend.simulation.platforms.base import AbstractPlatform


class RedditStartups(AbstractPlatform):
    name = "reddit_startups"
    allowed_actions = ["comment", "upvote", "downvote"]
    no_content_actions = {"upvote", "downvote"}
    system_prompt = (
        "You are a Reddit r/startups member. Be direct and sometimes skeptical. "
        "Challenge assumptions. Mention competitor products if relevant. "
        "Upvote insightful posts; downvote spam or unoriginal ideas. "
        "Comments should be conversational, not corporate."
    )

    def content_tool(self, action_type: str) -> dict:
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
                },
                "required": ["text", "contrarian_point"],
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
        text = structured_data.get("text", "")
        contrarian = structured_data.get("contrarian_point")
        if contrarian:
            return f"{text}\n\nCounter-point: {contrarian}"
        return text

    def extract_seed_content(self, structured_data: dict) -> str:
        title = structured_data.get("title", "")
        body = structured_data.get("body", "")
        return f"{title}\n\n{body}".strip() if body else title
