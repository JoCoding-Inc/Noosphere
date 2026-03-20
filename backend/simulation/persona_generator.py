# backend/simulation/persona_generator.py
from __future__ import annotations
import logging
import os
import anthropic
from backend.simulation.models import Persona
from backend.simulation.graph_utils import sanitize_neighbor_titles
from backend.simulation.rate_limiter import api_sem as _api_sem

logger = logging.getLogger(__name__)

_client: anthropic.AsyncAnthropic | None = None


def _get_client() -> anthropic.AsyncAnthropic:
    global _client
    if _client is None:
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY environment variable is not set."
            )
        _client = anthropic.AsyncAnthropic(api_key=api_key, timeout=30.0)
    return _client


# For academic sources, force low commercial_focus; others are LLM-decided
_FORCED_ATTRS_BY_SOURCE: dict[str, dict] = {
    "arxiv": {"commercial_focus": 1},
    "s2":    {"commercial_focus": 1},
}

_PLATFORM_AUDIENCE = {
    "hackernews": (
        "Hacker News — audience: software engineers, systems programmers, technical founders, "
        "open-source contributors, security researchers. They value technical depth, contrarianism, "
        "and dislike hype. Generate a persona typical of this community."
    ),
    "producthunt": (
        "Product Hunt — audience: early adopters, product managers, UX/UI designers, growth hackers, "
        "startup enthusiasts who love discovering new tools. They care about polish, novelty, and "
        "user experience. Generate a persona typical of this community."
    ),
    "indiehackers": (
        "Indie Hackers — audience: bootstrapped solo founders, micro-SaaS builders, freelancers turning "
        "products, people optimising for MRR and independence over VC funding. "
        "Generate a persona typical of this community."
    ),
    "reddit_startups": (
        "Reddit r/startups — audience: early-stage founders, first-time entrepreneurs, angel investors, "
        "startup employees at seed/Series-A companies. Mix of optimism and hard-won scepticism. "
        "Generate a persona typical of this community."
    ),
    "linkedin": (
        "LinkedIn — audience: enterprise executives, VPs, corporate managers, B2B sales professionals, "
        "HR leaders, investors looking at market trends. They think in terms of ROI, risk, and "
        "organisational impact. Generate a persona typical of this community."
    ),
}

_PERSONA_TOOL = {
    "name": "create_persona",
    "description": "Create a realistic, diverse persona for a knowledge node participant on a specific platform.",
    "input_schema": {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "Full name (culturally appropriate for the platform's likely audience)",
            },
            "role": {
                "type": "string",
                "description": "Specific job title (e.g. 'Senior Backend Engineer', 'Seed-stage VC Partner', 'ML Research Scientist')",
            },
            "age": {
                "type": "integer",
                "description": "Age in years (22-65). Must be consistent with seniority and years of experience.",
                "minimum": 22,
                "maximum": 65,
            },
            "seniority": {
                "type": "string",
                "enum": ["intern", "junior", "mid", "senior", "lead", "principal", "director", "vp", "c_suite"],
                "description": "Career seniority level",
            },
            "affiliation": {
                "type": "string",
                "enum": ["individual", "startup", "mid_size", "enterprise", "bigtech", "academic"],
                "description": "Type of organization this person is affiliated with",
            },
            "company": {
                "type": "string",
                "description": "Specific company name or descriptive label (e.g. 'Google', 'seed-stage fintech startup', 'MIT CSAIL', 'independent consultant')",
            },
            "mbti": {
                "type": "string",
                "description": "4-letter MBTI type (e.g. 'INTJ', 'ENFP')",
                "pattern": "^[IE][NS][TF][JP]$",
            },
            "interests": {
                "type": "array",
                "items": {"type": "string"},
                "description": "3-8 professional and personal interests relevant to this persona",
                "minItems": 3,
                "maxItems": 8,
            },
            "skepticism": {
                "type": "integer",
                "description": "Skepticism level: 1=enthusiastic evangelist, 10=extreme skeptic. Reflect how this type of person typically reacts to new ideas.",
                "minimum": 1,
                "maximum": 10,
            },
            "commercial_focus": {
                "type": "integer",
                "description": "Commercial orientation: 1=pure academic/idealistic (cares about truth/craft), 10=purely commercial/ROI-driven (cares about revenue/growth).",
                "minimum": 1,
                "maximum": 10,
            },
            "innovation_openness": {
                "type": "integer",
                "description": "Innovation openness: 1=very conservative/risk-averse (prefers proven solutions), 10=extreme early adopter (loves bleeding-edge, tolerates risk).",
                "minimum": 1,
                "maximum": 10,
            },
        },
        "required": [
            "name", "role", "age", "seniority", "affiliation", "company",
            "mbti", "interests", "skepticism", "commercial_focus", "innovation_openness",
        ],
    },
}

_SYSTEM_TMPL = """\
You are generating a realistic, diverse persona for a knowledge node in the context of a specific idea being evaluated.
Given a node (title, source, abstract), the idea being analyzed, and the target platform, create a realistic person who would have a meaningful perspective on that idea ON THAT PLATFORM.

Platform context: {platform_context}

Guidelines:
- The persona does NOT have to be someone who created or published the node. They should be the kind of person who would encounter this topic on the specified platform.
- Use the platform context to determine appropriate role, seniority, and affiliation. Personas across platforms should differ significantly.
- Age must be consistent with seniority (e.g. a c_suite persona should be 38+ years old, a junior persona 22-30).
- Make the persona feel like a real individual: specific company, realistic age, coherent interests.
- Vary skepticism, commercial_focus, and innovation_openness to reflect the diversity of real users on this platform."""


async def generate_persona(
    node: dict,
    idea_text: str = "",
    neighbor_titles: list[str] | None = None,
    platform_name: str = "",
) -> Persona:
    node_id = node.get("id")
    if not node_id:
        raise ValueError(f"Node missing required 'id' field: {node!r}")

    source = node.get("source", "")[:50].replace("\n", " ").replace("\r", " ")
    title = node.get("title", "")[:200].replace("\n", " ").replace("\r", " ")
    abstract = node.get("abstract", "")[:300].replace("\n", " ").replace("\r", " ")

    idea_snippet = idea_text.replace("\n", " ").replace("\r", " ") if idea_text else ""
    prompt = (
        f"Idea being evaluated: {idea_snippet}\n\n"
        f"Node — Title: {title}\n"
        f"Source: {source}\n"
        f"Abstract: {abstract}"
    )
    sanitized_neighbors = sanitize_neighbor_titles(neighbor_titles)
    if sanitized_neighbors:
        neighbor_str = ", ".join(sanitized_neighbors)
        prompt += f"\nNeighboring technologies (related nodes): {neighbor_str}"

    platform_context = _PLATFORM_AUDIENCE.get(
        platform_name,
        "A general online tech community. Generate a diverse persona appropriate to the idea's domain.",
    )
    system = _SYSTEM_TMPL.format(platform_context=platform_context)

    for attempt in range(4):
        try:
            async with _api_sem:
                message = await _get_client().messages.create(
                    model="claude-haiku-4-5-20251001",
                    max_tokens=8192,
                    system=system,
                    tools=[_PERSONA_TOOL],
                    tool_choice={"type": "tool", "name": "create_persona"},
                    messages=[{"role": "user", "content": prompt}],
                )
            break
        except anthropic.RateLimitError as exc:
            if attempt == 3:
                raise
            import asyncio as _asyncio
            wait = 5 * (2 ** attempt)
            logger.warning("Persona rate limit (attempt %d/4), retrying in %ds: %s", attempt + 1, wait, exc)
            await _asyncio.sleep(wait)
        except Exception as exc:
            if attempt == 1:
                raise
            logger.warning("Persona API call failed (attempt %d): %s — retrying", attempt + 1, exc)
            await __import__("asyncio").sleep(1.0)

    # Extract structured output from tool_use block
    tool_block = next(
        (b for b in message.content if b.type == "tool_use"),
        None,
    )
    if tool_block is None:
        raise ValueError(f"No tool_use block in persona response for node {node_id}")

    data: dict = tool_block.input

    # Apply forced attributes for academic sources
    forced = _FORCED_ATTRS_BY_SOURCE.get(source, {})

    # Normalize interests
    interests_raw = data.get("interests", [])
    if isinstance(interests_raw, str):
        interests = [t.strip() for t in interests_raw.split(",") if t.strip()]
    elif isinstance(interests_raw, list):
        interests = [str(i) for i in interests_raw]
    else:
        interests = []
    interests = interests[:8] or ["general"]

    return Persona(
        node_id=node_id,
        name=data.get("name", "Unknown"),
        role=data.get("role", "Professional"),
        age=int(data.get("age", 30)),
        seniority=data.get("seniority", "mid"),
        affiliation=data.get("affiliation", "individual"),
        company=data.get("company", ""),
        mbti=data.get("mbti", "INTJ"),
        interests=interests,
        skepticism=forced.get("skepticism", int(data.get("skepticism", 5))),
        commercial_focus=forced.get("commercial_focus", int(data.get("commercial_focus", 5))),
        innovation_openness=forced.get("innovation_openness", int(data.get("innovation_openness", 5))),
        source_title=node.get("title", ""),
    )
