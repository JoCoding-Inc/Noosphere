"""
Persona distribution selector.
Makes ONE lightweight LLM call to determine per-platform archetype distribution
based on the idea/topic, then selects matching agents from the pre-defined pool.
"""
from __future__ import annotations

import json
import logging
import random
from typing import Any

logger = logging.getLogger(__name__)

# ── Default distributions per platform ───────────────────────────────────────

PLATFORM_DEFAULT_DISTRIBUTIONS: dict[str, dict[str, float]] = {
    "hackernews": {
        "developer": 0.40,
        "researcher": 0.15,
        "startup": 0.20,
        "investor": 0.10,
        "marketer": 0.05,
        "designer": 0.05,
        "business": 0.05,
    },
    "reddit": {
        "developer": 0.25,
        "researcher": 0.10,
        "startup": 0.10,
        "investor": 0.05,
        "marketer": 0.10,
        "designer": 0.10,
        "business": 0.05,
        "general": 0.25,
    },
    "reddit_startups": {
        "developer": 0.20,
        "researcher": 0.08,
        "startup": 0.35,
        "investor": 0.10,
        "marketer": 0.12,
        "designer": 0.05,
        "business": 0.05,
        "general": 0.05,
    },
    "producthunt": {
        "startup": 0.30,
        "developer": 0.20,
        "investor": 0.15,
        "marketer": 0.15,
        "designer": 0.10,
        "business": 0.05,
        "researcher": 0.05,
    },
    "indiehackers": {
        "startup": 0.40,
        "developer": 0.35,
        "marketer": 0.10,
        "designer": 0.08,
        "investor": 0.07,
    },
    "linkedin": {
        "business": 0.20,
        "marketer": 0.20,
        "investor": 0.15,
        "startup": 0.10,
        "developer": 0.15,
        "designer": 0.10,
        "researcher": 0.10,
    },
}

_DISTRIBUTION_PROMPT = """\
You are a market research expert. Given a product/idea description, determine the most likely audience distribution across archetypes for each platform listed below.

Product/Idea: {idea_text}

Platforms: {platforms}

Available archetypes: developer, researcher, startup, investor, marketer, designer, business, general

Return a JSON object where keys are platform names and values are objects mapping archetype to ratio (0.0-1.0). Ratios for each platform must sum to 1.0. Only include platforms listed above. Adjust distributions based on the product domain — e.g. a deep-tech AI research tool would have more researcher/developer weight; a consumer app would have more general/marketer weight.

Return ONLY valid JSON, no other text."""


async def get_distribution(
    idea_text: str,
    platforms: list[str],
    llm: Any,
) -> dict[str, dict[str, float]]:
    """
    Makes ONE gpt-4.1-mini call to adjust default distributions per platform based on idea_text.
    Returns a mapping of platform -> archetype -> ratio.
    Falls back to defaults if LLM call fails.
    """
    # Build defaults for requested platforms
    defaults: dict[str, dict[str, float]] = {}
    for platform in platforms:
        defaults[platform] = dict(
            PLATFORM_DEFAULT_DISTRIBUTIONS.get(platform, PLATFORM_DEFAULT_DISTRIBUTIONS["hackernews"])
        )

    if not idea_text or not idea_text.strip():
        return defaults

    prompt = _DISTRIBUTION_PROMPT.format(
        idea_text=idea_text[:500],
        platforms=", ".join(platforms),
    )

    try:
        response = await llm.complete(
            messages=[{"role": "user", "content": prompt}],
            tier="low",
            max_tokens=512,
        )
        raw = (response.content or "").strip()

        # Strip markdown code fences if present
        if raw.startswith("```"):
            lines = raw.splitlines()
            raw = "\n".join(
                line for line in lines
                if not line.startswith("```")
            ).strip()

        parsed: dict = json.loads(raw)

        result: dict[str, dict[str, float]] = {}
        for platform in platforms:
            if platform in parsed and isinstance(parsed[platform], dict):
                dist = {k: float(v) for k, v in parsed[platform].items() if isinstance(v, (int, float))}
                # Normalize to sum = 1.0
                total = sum(dist.values())
                if total > 0:
                    dist = {k: v / total for k, v in dist.items()}
                    result[platform] = dist
                else:
                    result[platform] = defaults[platform]
            else:
                result[platform] = defaults[platform]

        logger.info("LLM distribution adjustment succeeded for platforms: %s", platforms)
        return result

    except Exception as exc:
        logger.warning("LLM distribution call failed (%s), using defaults", exc)
        return defaults


def select_agents_for_platform(
    platform: str,
    n: int,
    distribution: dict[str, float],
    pool: list[dict],
    used_names: set[str],
) -> list[dict]:
    """
    Select n agents from the pool matching the given archetype distribution.
    Avoids names already in `used_names` (cross-platform deduplication).
    Adds selected names to `used_names`.
    Falls back to random selection if not enough matching agents are available.
    """
    if n <= 0:
        return []

    # Build per-archetype sub-pools (excluding used names)
    arch_pool: dict[str, list[dict]] = {}
    for agent in pool:
        arch = agent.get("archetype", "general")
        name = agent.get("name", "")
        if name not in used_names:
            arch_pool.setdefault(arch, []).append(agent)

    # Shuffle each sub-pool for randomness
    for arch in arch_pool:
        random.shuffle(arch_pool[arch])

    selected: list[dict] = []

    # Determine target counts per archetype
    archetype_targets: dict[str, int] = {}
    remaining_slots = n
    sorted_archetypes = sorted(distribution.items(), key=lambda x: -x[1])  # highest ratio first

    for i, (arch, ratio) in enumerate(sorted_archetypes):
        if i == len(sorted_archetypes) - 1:
            # Last archetype gets all remaining slots
            archetype_targets[arch] = remaining_slots
        else:
            count = round(ratio * n)
            count = min(count, remaining_slots)
            archetype_targets[arch] = count
            remaining_slots -= count
            if remaining_slots <= 0:
                break

    # Select agents per archetype
    for arch, target_count in archetype_targets.items():
        if target_count <= 0:
            continue
        available = arch_pool.get(arch, [])
        take = min(target_count, len(available))
        batch = available[:take]
        selected.extend(batch)
        # Mark as used
        for agent in batch:
            used_names.add(agent["name"])
        # Track shortfall for fallback
        shortfall = target_count - take

        if shortfall > 0:
            # Try adjacent archetypes to fill shortfall
            for fallback_arch, fallback_agents in arch_pool.items():
                if fallback_arch == arch or shortfall <= 0:
                    break
                remaining_in_fallback = [a for a in fallback_agents if a["name"] not in used_names]
                take_fallback = min(shortfall, len(remaining_in_fallback))
                batch = remaining_in_fallback[:take_fallback]
                selected.extend(batch)
                for agent in batch:
                    used_names.add(agent["name"])
                shortfall -= take_fallback

    # If still short, random fill from any unused agent
    if len(selected) < n:
        all_unused = [a for a in pool if a.get("name", "") not in used_names]
        random.shuffle(all_unused)
        gap = n - len(selected)
        extra = all_unused[:gap]
        selected.extend(extra)
        for agent in extra:
            used_names.add(agent["name"])

    # Shuffle so archetypes are interleaved, not grouped
    random.shuffle(selected)
    return selected[:n]
