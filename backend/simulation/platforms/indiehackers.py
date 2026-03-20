from backend.simulation.platforms.base import AbstractPlatform


class IndieHackers(AbstractPlatform):
    name = "indiehackers"
    allowed_actions = ["comment", "share_experience", "ask_advice"]
    no_content_actions: set = set()
    system_prompt = (
        "You are an IndieHackers member — a bootstrapper or solo founder. "
        "Focus on revenue, retention, and real-world execution. "
        "Share personal experience. Ask about monetization and growth. "
        "Be supportive but honest about risks."
    )

    def content_tool(self, action_type: str) -> dict:
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
                    },
                    "required": ["text", "mrr_context", "lesson"],
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
                    },
                    "required": ["text", "specific_question"],
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
                },
                "required": ["text"],
            },
        }

    def seed_tool(self) -> dict:
        return {
            "name": "create_seed_post",
            "description": "Write an Indie Hackers post introducing a product idea.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Post title — clear, specific, outcome-oriented.",
                    },
                    "body": {
                        "type": "string",
                        "description": "Post body covering the problem, solution, and current stage. 3-5 sentences.",
                    },
                    "stage": {
                        "type": "string",
                        "enum": ["idea", "building", "launched", "growing"],
                        "description": "Current stage of the product.",
                    },
                },
                "required": ["title", "body", "stage"],
            },
        }

    def extract_content(self, action_type: str, structured_data: dict) -> str:
        text = structured_data.get("text", "")
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
        title = structured_data.get("title", "")
        body = structured_data.get("body", "")
        stage = structured_data.get("stage", "")
        parts = [p for p in [title, body, f"Stage: {stage}" if stage else ""] if p]
        return "\n\n".join(parts)
