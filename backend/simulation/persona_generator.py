# backend/simulation/persona_generator.py
from __future__ import annotations
import logging
import random
from backend.simulation.models import Persona
from backend import llm
from backend.llm import LLMToolRequired
from backend.ontology_builder import ontology_for_persona

logger = logging.getLogger(__name__)


# For academic sources, force low commercial_focus; others are LLM-decided
_FORCED_ATTRS_BY_SOURCE: dict[str, dict] = {
    "arxiv": {"commercial_focus": 1},
    "s2":    {"commercial_focus": 1},
}

_PLATFORM_AUDIENCE = {
    "hackernews": (
        "Hacker News — community of curious, technically-literate people. "
        "Pick ONE of these archetypes at random (do not default to engineer): "
        "software engineer, indie hacker (solo product builder), "
        "seed-stage VC analyst, non-technical founder, "
        "marketer at a dev-tool company, hobbyist coder (teacher / cafe owner / designer who codes on the side), "
        "product manager, academic researcher, security professional, open-source maintainer. "
        "They all share intellectual curiosity and skepticism of hype. Generate a persona typical of this community."
    ),
    "producthunt": (
        "Product Hunt — audience discovering new products. "
        "Pick ONE of these archetypes: "
        "UX/UI designer, early adopter (non-technical), product manager, growth hacker, "
        "startup founder (non-technical), indie maker, journalist covering tech, "
        "community manager, developer advocate, small business owner. "
        "They care about polish, novelty, and user experience. Generate a persona typical of this community."
    ),
    "indiehackers": (
        "Indie Hackers — bootstrapped builders. "
        "Pick ONE of these archetypes: "
        "solo founder running a micro-SaaS, freelancer productizing a service, "
        "developer with a side project, consultant building passive income, "
        "ex-corporate employee going independent, designer turned founder, "
        "non-technical founder learning to code, creator monetizing an audience. "
        "They optimize for MRR and independence over VC funding. Generate a persona typical of this community."
    ),
    "reddit_startups": (
        "Reddit r/startups — mix of early-stage builders and observers. "
        "Pick ONE of these archetypes: "
        "first-time founder, startup employee (sales / ops / marketing), angel investor, "
        "MBA student interested in entrepreneurship, product manager at a Series A, "
        "developer considering leaving their job, domain expert starting a company, "
        "journalist or blogger covering startups. "
        "Mix of optimism and hard-won scepticism. Generate a persona typical of this community."
    ),
    "linkedin": (
        "LinkedIn — professional network for enterprise and career. "
        "Pick ONE of these archetypes: "
        "VP at a mid-size company, enterprise sales director, HR leader, "
        "corporate strategy consultant, B2B marketing manager, CTO at a 200-person company, "
        "VC partner focused on Series B+, procurement officer, "
        "industry analyst, chief digital officer. "
        "They think in terms of ROI, risk, and organisational impact. Generate a persona typical of this community."
    ),
}

_PERSONA_TOOL = {
    "type": "function",
    "function": {
        "name": "create_persona",
        "description": "Create a realistic, diverse persona for a knowledge node participant on a specific platform.",
        "parameters": {
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
                "domain_type": {
                    "type": "string",
                    "enum": ["tech", "research", "consumer", "business", "healthcare", "general"],
                    "description": "Primary domain type of this persona's expertise and interest",
                },
                "tech_area": {
                    "type": "array",
                    "items": {"type": "string", "enum": ["AI/ML", "cloud", "security", "data", "mobile", "web", "hardware", "other"]},
                    "description": "1-2 tech areas this persona focuses on",
                    "minItems": 0,
                    "maxItems": 2,
                },
                "market": {
                    "type": "array",
                    "items": {"type": "string", "enum": ["B2B", "B2C", "enterprise", "developer", "consumer", "academic"]},
                    "description": "1-2 market segments this persona operates in",
                    "minItems": 0,
                    "maxItems": 2,
                },
                "problem_domain": {
                    "type": "array",
                    "items": {"type": "string", "enum": ["automation", "analytics", "communication", "productivity", "infrastructure", "security", "UX", "compliance"]},
                    "description": "1-2 problem domains this persona cares about",
                    "minItems": 0,
                    "maxItems": 2,
                },
            },
            "required": [
                "name", "role", "age", "seniority", "affiliation", "company",
                "mbti", "interests", "skepticism", "commercial_focus", "innovation_openness",
            ],
        },
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
- Vary skepticism, commercial_focus, and innovation_openness to reflect the diversity of real users on this platform.
- Vary MBTI type across personas. Do NOT cluster on INTJ. Choose from the full 16 types; prefer less common types for variety."""


_FALLBACK_NAMES = [
    "Alex Morgan", "Sam Rivera", "Jordan Lee", "Casey Kim",
    "Taylor Nguyen", "Morgan Chen", "Riley Patel", "Drew Santos",
    "Quinn Yamamoto", "Avery Okafor",
]
_FALLBACK_MBTIS = ["INTJ", "INTP", "ENTP", "ENFP", "ISTJ", "ESTJ", "ISTP", "INFJ"]


def _fallback_persona(cluster: dict, platform_name: str) -> Persona:
    rep = cluster.get("representative") or {}
    return Persona(
        node_id=cluster.get("id", "unknown"),
        name=random.choice(_FALLBACK_NAMES),
        role="Software Engineer",
        age=30,
        seniority="mid",
        affiliation="individual",
        company="",
        mbti=random.choice(_FALLBACK_MBTIS),
        interests=["technology"],
        skepticism=5,
        commercial_focus=5,
        innovation_openness=5,
        source_title=rep.get("title", ""),
        domain_type="",
        tech_area=[],
        market=[],
        problem_domain=[],
    )


def _normalize_cluster_input(cluster_or_node: dict) -> dict:
    """Accept either a cluster dict or a legacy single-node dict."""
    if cluster_or_node.get("nodes") is not None or cluster_or_node.get("representative") is not None:
        return cluster_or_node
    node_id = cluster_or_node.get("id", "unknown")
    return {
        "id": node_id,
        "nodes": [cluster_or_node] if cluster_or_node else [],
        "representative": cluster_or_node,
    }


async def generate_persona(
    cluster: dict,
    idea_text: str = "",
    platform_name: str = "",
    provider: str = "openai",
    ontology: dict | None = None,
) -> Persona:
    cluster = _normalize_cluster_input(cluster)
    cluster_id = cluster.get("id", "unknown")
    nodes: list[dict] = cluster.get("nodes", [])
    representative: dict = cluster.get("representative") or (nodes[0] if nodes else {})

    rep_source = representative.get("source", "")[:50].replace("\n", " ").replace("\r", " ")
    rep_title = representative.get("title", "")[:200].replace("\n", " ").replace("\r", " ")
    rep_abstract = representative.get("abstract", "")[:300].replace("\n", " ").replace("\r", " ")

    other_titles = ", ".join(
        n.get("title", "")[:80].replace("\n", " ")
        for n in nodes
        if n.get("id") != representative.get("id") and n.get("title")
    )[:300]

    idea_snippet = idea_text.replace("\n", " ").replace("\r", " ") if idea_text else ""
    prompt = (
        f"Idea being evaluated: {idea_snippet}\n\n"
        f"Knowledge cluster — Representative: [{rep_source}] {rep_title}\n"
        f"Background: {rep_abstract}"
    )
    if other_titles:
        prompt += f"\nRelated topics in this cluster: {other_titles}"
    if ontology:
        prompt += f"\n\nLegacy ecosystem context:\n{ontology_for_persona(ontology)}"

    platform_context = _PLATFORM_AUDIENCE.get(
        platform_name,
        "A general online tech community. Generate a diverse persona appropriate to the idea's domain.",
    )
    system = _SYSTEM_TMPL.format(platform_context=platform_context)

    try:
        response = await llm.complete(
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            tier="mid",
            provider=provider,
            max_tokens=4096,
            tools=[_PERSONA_TOOL],
            tool_choice="create_persona",
        )
        data = response.tool_args
    except LLMToolRequired:
        raise
    except Exception as exc:
        logger.warning("generate_persona failed: %s", exc)
        return _fallback_persona(cluster, platform_name)

    # Apply forced attributes for academic sources
    forced = _FORCED_ATTRS_BY_SOURCE.get(rep_source, {})

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
        node_id=cluster_id,
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
        source_title=rep_title,
        domain_type=str(data.get("domain_type", "")),
        tech_area=list(data.get("tech_area") or []),
        market=list(data.get("market") or []),
        problem_domain=list(data.get("problem_domain") or []),
    )
