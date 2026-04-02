# backend/simulation/persona_generator.py
from __future__ import annotations
import logging
import random
from backend.simulation.models import Persona
from backend.simulation.taxonomy import (
    coerce_enum,
    coerce_string_list,
    DOMAIN_TYPES,
    TECH_AREAS,
    MARKETS,
    PROBLEM_DOMAINS,
)
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
        "product manager, academic researcher, security professional, open-source maintainer, "
        "CFO at a startup (evaluates ROI and burn rate), CISO (evaluates security implications first). "
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
        "industry analyst, chief digital officer, "
        "CMO thinking about channel differentiation and positioning, "
        "CFO running unit economics and CAC/LTV analysis, "
        "CPO evaluating problem-solution fit over feature completeness, "
        "CTO defaulting to monolith thinking — 'do we need this complexity?'. "
        "They think in terms of ROI, risk, and organisational impact. Generate a persona typical of this community."
    ),
}


import re as _re

# Extract archetype lists from _PLATFORM_AUDIENCE for Python-controlled selection
_PLATFORM_ARCHETYPES: dict[str, list[str]] = {}
for _plat_key, _plat_desc in _PLATFORM_AUDIENCE.items():
    # Find text between "Pick ONE of these archetypes" variants and the period that ends the list
    _match = _re.search(
        r"Pick ONE (?:of these archetypes|at random)[^:]*:\s*(.+?)(?:\.\s*They|\.\s*Mix|\.\s*Generate)",
        _plat_desc,
        _re.DOTALL,
    )
    if _match:
        _raw = _match.group(1)
        _archs = [a.strip().rstrip(".") for a in _raw.split(",") if a.strip()]
        _PLATFORM_ARCHETYPES[_plat_key] = _archs

_DEFAULT_ARCHETYPES: list[str] = [
    "early adopter", "skeptic", "domain expert", "founder",
    "investor", "operator", "researcher", "product manager",
]


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
                "jtbd": {
                    "type": "string",
                    "description": "Job-to-be-Done: what is this persona fundamentally trying to accomplish when they encounter this product idea? (1-2 sentences, specific and actionable)",
                },
                "cognitive_pattern": {
                    "type": "string",
                    "description": "Dominant cognitive lens this persona uses to evaluate new ideas. Examples: 'Inversion first — asks how this fails before considering upside', 'ROI gate — every idea must show unit economics', 'JTBD purist — only cares if this replaces something they already do', 'Early adopter bias — default yes unless there is a hard blocker'. Be specific to the persona's role and background.",
                },
                "emotional_state": {
                    "type": "string",
                    "description": "Emotional context when this persona encounters this product idea (1 short phrase). Examples: 'cautiously optimistic', 'skeptical but FOMO-aware', 'excited but budget-constrained', 'burned before by hype cycles'.",
                },
                "region": {
                    "type": "string",
                    "enum": ["NA", "EU", "APAC", "LATAM", "MENA", "Global"],
                    "description": "Geographic region representing this persona's primary market perspective",
                },
            },
            "required": [
                "name", "role", "age", "seniority", "affiliation", "company",
                "mbti", "interests", "skepticism", "commercial_focus", "innovation_openness",
                "domain_type", "tech_area", "market", "problem_domain",
                "jtbd", "cognitive_pattern", "emotional_state", "region",
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
- Vary MBTI type across personas. Do NOT cluster on INTJ. Choose from the full 16 types; prefer less common types for variety.
- For jtbd: think about what specific outcome this person is trying to achieve in their professional life that makes this idea relevant (or irrelevant) to them. Ground it in their role, seniority, and platform context.
- For cognitive_pattern: pick the ONE dominant mental model this type of person uses first when evaluating new tools or products. Make it specific, not generic.
- For emotional_state: capture the underlying feeling that colors how they approach new product ideas, given their career stage and past experiences.
- Include geographic diversity - each persona should reflect their region's specific regulatory environment, market maturity, and pricing expectations."""


_NAME_POOL = [
    # East Asian
    "Wei Zhang", "Yuki Tanaka", "Ji-ho Kim", "Anh Nguyen", "Mei Lin",
    "Hiroshi Kato", "Soo-yeon Park", "Linh Tran", "Jae-won Choi", "Ren Yamamoto",
    "Xiao Chen", "Hana Watanabe", "Min-jun Lee", "Thuy Pham", "Ryo Suzuki",
    # South Asian
    "Arjun Sharma", "Priya Patel", "Rahul Gupta", "Ananya Iyer", "Vikram Nair",
    "Shreya Krishnan", "Rohan Mehta", "Kavya Reddy", "Aditya Singh", "Neha Joshi",
    # Western — English-speaking
    "James Wilson", "Sarah Johnson", "Michael Brown", "Emma Davis", "Ethan Miller",
    "Olivia Taylor", "Noah Anderson", "Ava Thomas", "Liam Jackson", "Sophia White",
    "William Harris", "Isabella Martin", "Benjamin Thompson", "Mia Garcia", "Lucas Martinez",
    "Charlotte Robinson", "Henry Lewis", "Amelia Walker", "Alexander Hall", "Harper Young",
    "Daniel King", "Evelyn Wright", "Matthew Scott", "Abigail Green", "Aiden Baker",
    "Emily Adams", "Jackson Nelson", "Elizabeth Carter", "Sebastian Mitchell", "Chloe Perez",
    # African / Afro-American
    "Amara Osei", "Kwame Mensah", "Zara Adeyemi", "Kofi Owusu", "Nadia Diallo",
    "Emeka Okonkwo", "Fatou Sow", "Chidi Obi", "Aisha Kamara", "Seun Adewale",
    "Tunde Okafor", "Blessing Nwosu", "Yaw Asante", "Chiamaka Eze", "Babatunde Alabi",
    # Hispanic / Latino
    "Diego Martínez", "Sofía Rodríguez", "Carlos Flores", "Valentina López", "Andrés Torres",
    "Camila Herrera", "Mateo Jiménez", "Isabela Morales", "Santiago Romero", "Daniela Vargas",
    # Middle Eastern / North African
    "Layla Hassan", "Omar Khalil", "Yasmin Nasser", "Tariq Al-Rashid", "Nour Aziz",
    "Khalid Ibrahim", "Fatima Al-Zahra", "Rami Haddad", "Leila Mansour", "Ziad Farouk",
    # Eastern European
    "Aleksei Petrov", "Natasha Volkov", "Dmitri Sokolov", "Irina Kozlov", "Pavel Novak",
    "Katarzyna Wiśniewska", "Marek Kowalski", "Zuzanna Horváth", "Tomáš Novotný", "Monika Jovanović",
    # Misc / other
    "Matías Oliveira", "Ingrid Svensson", "Finn Andersen", "Elif Yıldız", "Yusuf Demir",
    "Aarav Kapoor", "Riya Desai", "Kenji Oshiro", "Minji Yoon", "Takeshi Nakamura",
]

_FALLBACK_NAMES = _NAME_POOL[:10]  # kept for backward-compat


def sample_persona_names(n: int) -> list[str]:
    """Return n unique names sampled from the pool without replacement.

    If n exceeds the pool size, additional names are generated by cycling
    through a reshuffled pool so callers always get exactly n names.
    """
    pool = list(_NAME_POOL)
    random.shuffle(pool)
    if n <= len(pool):
        return pool[:n]
    result = pool[:]
    while len(result) < n:
        random.shuffle(pool)
        result.extend(pool)
    return result[:n]
_FALLBACK_MBTIS = ["INTJ", "INTP", "ENTP", "ENFP", "ISTJ", "ESTJ", "ISTP", "INFJ"]
_FALLBACK_REGIONS = ["NA", "EU", "APAC", "LATAM", "MENA", "Global"]


import random as _random


def _validate_persona_distribution(personas: list[Persona]) -> list[Persona]:
    """Post-process a batch of personas to ensure skepticism/region/MBTI diversity.

    Mutates personas in-place and returns the same list.
    """
    if not personas:
        return personas

    # 1. skepticism 극단값 보장 (1-3: 최소 15%, 7-10: 최소 20%)
    low_skept = [p for p in personas if p.skepticism and p.skepticism <= 3]
    high_skept = [p for p in personas if p.skepticism and p.skepticism >= 7]
    mid_skept = [p for p in personas if p.skepticism and 4 <= p.skepticism <= 6]
    n = len(personas)

    target_low = max(1, int(n * 0.15))
    target_high = max(1, int(n * 0.20))

    # mid가 너무 많으면 일부를 극단으로 재배정
    while len(low_skept) < target_low and mid_skept:
        p = mid_skept.pop()
        p.skepticism = _random.randint(1, 3)
        low_skept.append(p)
    while len(high_skept) < target_high and mid_skept:
        p = mid_skept.pop()
        p.skepticism = _random.randint(7, 10)
        high_skept.append(p)

    # 2. region 다양성 보장 (최소 3개 지역)
    regions = [p.region for p in personas if p.region]
    unique_regions = set(regions)
    # 방어: region이 모두 비어있으면 순환 배정
    if not unique_regions and len(personas) >= 5:
        _all_regions_pool = ["NA", "EU", "APAC", "LATAM", "MENA"]
        for i, p in enumerate(personas):
            p.region = _all_regions_pool[i % len(_all_regions_pool)]
        regions = [p.region for p in personas]
        unique_regions = set(regions)
    if len(unique_regions) < 3 and len(personas) >= 5:
        all_regions = ["NA", "EU", "APAC", "LATAM", "MENA"]
        missing = [r for r in all_regions if r not in unique_regions]
        dominant = max(unique_regions, key=lambda r: regions.count(r)) if unique_regions else "NA"
        dominant_personas = [p for p in personas if p.region == dominant]
        for i, region in enumerate(missing[:2]):  # 최대 2개 지역 추가
            if i < len(dominant_personas):
                dominant_personas[i].region = region

    # 3. Role diversity check: dominant keyword > 40% of count -> warning log
    if len(personas) >= 5:
        role_words: list[str] = []
        for p in personas:
            words = (p.role or "").lower().split()
            role_words.extend(words[:2])  # first 2 words only
        from collections import Counter
        role_counter = Counter(role_words)
        if role_counter:
            most_common_word, most_common_count = role_counter.most_common(1)[0]
            if most_common_count / len(personas) > 0.4:
                logger.warning(
                    "Role diversity low: '%s' appears in %d/%d personas",
                    most_common_word, most_common_count, len(personas),
                )

    # 4. MBTI 다양성 보장 (최소 4종)
    mbtis = [p.mbti for p in personas if p.mbti]
    unique_mbtis = set(mbtis)
    if len(unique_mbtis) < 4 and len(personas) >= 6:
        all_mbtis = ["INTJ", "ENTJ", "INFP", "ENFP", "ISTJ", "ESTJ", "INTP", "ENTP", "ISFJ", "ESFJ"]
        missing_mbtis = [m for m in all_mbtis if m not in unique_mbtis]
        dominant_mbti = max(unique_mbtis, key=lambda m: mbtis.count(m)) if unique_mbtis else "INTJ"
        dominant_ps = [p for p in personas if p.mbti == dominant_mbti]
        for i, mbti in enumerate(missing_mbtis[:2]):
            if i < len(dominant_ps) // 2:  # 과반수는 유지
                dominant_ps[i].mbti = mbti

    return personas


def _validate_age_seniority(persona: Persona) -> Persona:
    """Post-process persona to ensure age/seniority consistency."""
    role_lower = (persona.role or "").lower()

    # Senior roles: c-suite, vp, director → age >= 35
    senior_keywords = ("c-suite", "ceo", "cto", "cfo", "chief", "vp", "vice president", "director")
    if any(kw in role_lower for kw in senior_keywords):
        if persona.age < 35:
            persona.age = 35

    # Junior roles: intern, junior, entry → age <= 40
    junior_keywords = ("intern", "junior", "entry")
    if any(kw in role_lower for kw in junior_keywords):
        if persona.age > 40:
            persona.age = 40

    # Seniority 기반 최소/최대 나이 보정 (role 키워드 검증 외에 추가)
    _seniority_age_constraints: dict[str, tuple[str, int]] = {
        "c_suite": ("min", 38),
        "vp": ("min", 38),
        "director": ("min", 33),
        "principal": ("min", 33),
        "lead": ("min", 28),
        "senior": ("min", 28),
        "intern": ("max", 28),
    }
    seniority = getattr(persona, "seniority", None)
    if seniority and seniority in _seniority_age_constraints:
        constraint_type, constraint_age = _seniority_age_constraints[seniority]
        if constraint_type == "min":
            persona.age = max(persona.age, constraint_age)
        else:
            persona.age = min(persona.age, constraint_age)

    # Global clamp: 22-65
    persona.age = max(22, min(65, persona.age))

    return persona


def _fallback_persona(cluster: dict, platform_name: str) -> Persona:
    rep = cluster.get("representative") or {}

    # Extract taxonomy from cluster's representative structured fields
    domain_type = coerce_enum(rep.get("_domain_type"), DOMAIN_TYPES) or "general"
    tech_area = coerce_string_list(rep.get("_tech_area"), allowed=TECH_AREAS, max_items=2)
    market = coerce_string_list(rep.get("_market"), allowed=MARKETS, max_items=2)
    problem_domain = coerce_string_list(rep.get("_problem_domain"), allowed=PROBLEM_DOMAINS, max_items=2)

    # Build a contextual jtbd from the domain
    domain_label = domain_type if domain_type != "general" else "technology"
    jtbd = f"Exploring solutions to {domain_label} challenges"

    persona = Persona(
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
        domain_type=domain_type,
        tech_area=tech_area,
        market=market,
        problem_domain=problem_domain,
        jtbd=jtbd,
        cognitive_pattern="analytical",
        emotional_state="curious",
        region=random.choice(_FALLBACK_REGIONS),
    )
    return _validate_age_seniority(persona)


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
    ontology: dict | None = None,
    assigned_name: str | None = None,
    domain_info: str = "",
    competitor_context: str = "",
    forced_archetype: str = "",
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

    # Python-controlled archetype selection to prevent LLM bias toward "software engineer"
    archetypes = _PLATFORM_ARCHETYPES.get(platform_name, [])
    if forced_archetype:
        selected_archetype = forced_archetype
    elif archetypes:
        selected_archetype = random.choice(archetypes)
    else:
        selected_archetype = ""
    if selected_archetype:
        # Replace "Pick ONE ... at random" instruction with a deterministic directive
        new_ctx = _re.sub(
            r"Pick ONE (?:of these archetypes|at random)[^.]*\.",
            f"You MUST generate a persona of archetype: {selected_archetype}.",
            platform_context,
        )
        if new_ctx == platform_context:
            # No regex match (e.g. platform not in _PLATFORM_AUDIENCE) — append directive
            platform_context += f" You MUST generate a persona of archetype: {selected_archetype}."
        else:
            platform_context = new_ctx

    domain_context = f"\nDomain context: {domain_info}" if domain_info else ""
    competitor_ctx = f"\nKey entities in this space: {competitor_context}. Reflect awareness of these alternatives in jtbd and cognitive_pattern." if competitor_context else ""
    system = _SYSTEM_TMPL.format(platform_context=platform_context) + domain_context + competitor_ctx

    try:
        response = await llm.complete(
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            tier="mid",
            max_tokens=4096,
            tools=[_PERSONA_TOOL],
            tool_choice="create_persona",
        )
        data = response.tool_args or {}
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
        interests = [
            t.strip() for t in interests_raw.replace("\n", ",").replace(";", ",").split(",")
            if t.strip()
        ]
    elif isinstance(interests_raw, list):
        interests = [str(i) for i in interests_raw]
    else:
        interests = []
    interests = interests[:8] or ["general"]

    domain_type = coerce_enum(data.get("domain_type"), DOMAIN_TYPES)
    tech_area = coerce_string_list(data.get("tech_area"), allowed=TECH_AREAS, max_items=2)
    market = coerce_string_list(data.get("market"), allowed=MARKETS, max_items=2)
    problem_domain = coerce_string_list(data.get("problem_domain"), allowed=PROBLEM_DOMAINS, max_items=2)

    persona = Persona(
        node_id=cluster_id,
        name=assigned_name or data.get("name", "Unknown"),
        role=data.get("role", "Professional"),
        age=int(data.get("age") or 30),
        seniority=data.get("seniority", "mid"),
        affiliation=data.get("affiliation", "individual"),
        company=data.get("company", ""),
        mbti=data.get("mbti", "INTJ"),
        interests=interests,
        skepticism=forced.get("skepticism", int(data.get("skepticism", 5))),
        commercial_focus=forced.get("commercial_focus", int(data.get("commercial_focus", 5))),
        innovation_openness=forced.get("innovation_openness", int(data.get("innovation_openness", 5))),
        source_title=rep_title,
        domain_type=domain_type,
        tech_area=tech_area,
        market=market,
        problem_domain=problem_domain,
        jtbd=data.get("jtbd", ""),
        cognitive_pattern=data.get("cognitive_pattern", ""),
        emotional_state=data.get("emotional_state", ""),
        region=data.get("region", ""),
    )
    return _validate_age_seniority(persona)
