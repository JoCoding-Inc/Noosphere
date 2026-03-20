from backend.simulation.platforms.base import AbstractPlatform


class LinkedIn(AbstractPlatform):
    name = "linkedin"
    allowed_actions = ["comment", "react", "share"]
    no_content_actions = {"react"}
    system_prompt = (
        "You are a LinkedIn professional — executive, investor, or domain expert. "
        "Write in a professional, structured tone. "
        "Comments should offer business insight or strategic perspective. "
        "Shares should add your own framing. React with Like or Insightful."
    )

    def content_tool(self, action_type: str) -> dict:
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
                    },
                    "required": ["text", "business_insight", "hashtags"],
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
                },
                "required": ["text", "stance"],
            },
        }

    def seed_tool(self) -> dict:
        return {
            "name": "create_seed_post",
            "description": "Write a LinkedIn post introducing a product idea to a professional audience.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "hook": {
                        "type": "string",
                        "description": "Attention-grabbing opening line or question. 1 sentence.",
                    },
                    "body": {
                        "type": "string",
                        "description": "Main content covering the problem, solution, and market opportunity. 3-4 sentences.",
                    },
                    "call_to_action": {
                        "type": "string",
                        "description": "Closing CTA inviting comments, connections, or discussion.",
                    },
                },
                "required": ["hook", "body", "call_to_action"],
            },
        }

    def extract_content(self, action_type: str, structured_data: dict) -> str:
        text = structured_data.get("text", "")
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
        hook = structured_data.get("hook", "")
        body = structured_data.get("body", "")
        cta = structured_data.get("call_to_action", "")
        parts = [p for p in [hook, body, cta] if p]
        return "\n\n".join(parts)
