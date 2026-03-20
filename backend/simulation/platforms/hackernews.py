from backend.simulation.platforms.base import AbstractPlatform


class HackerNews(AbstractPlatform):
    name = "hackernews"
    allowed_actions = ["comment", "reply", "upvote", "flag"]
    no_content_actions = {"upvote", "flag"}
    system_prompt = (
        "You are a Hacker News user. Be technical, concise, and intellectually rigorous. "
        "Prefer short, substantive comments. Ask clarifying questions. "
        "Skepticism is the default. Avoid hype. Flag irrelevant posts."
    )

    def content_tool(self, action_type: str) -> dict:
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
                },
                "required": ["text", "is_question"],
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
                    "text": {
                        "type": "string",
                        "description": "Optional body text (Ask HN / Show HN style). Can be empty for link submissions.",
                    },
                },
                "required": ["title", "text"],
            },
        }

    def extract_content(self, action_type: str, structured_data: dict) -> str:
        return structured_data.get("text", "")

    def extract_seed_content(self, structured_data: dict) -> str:
        title = structured_data.get("title", "")
        body = structured_data.get("text", "")
        return f"{title}\n\n{body}".strip() if body else title
