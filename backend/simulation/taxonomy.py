"""backend/simulation/taxonomy.py

Shared taxonomy constants and coercion helpers used across the simulation
pipeline. Import from here instead of duplicating in each module.
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DOMAIN_TYPES: set[str] = {"tech", "research", "consumer", "business", "healthcare", "general"}
TECH_AREAS: set[str] = {"AI/ML", "cloud", "security", "data", "mobile", "web", "hardware", "other"}
MARKETS: set[str] = {"B2B", "B2C", "enterprise", "developer", "consumer", "academic"}
PROBLEM_DOMAINS: set[str] = {
    "automation", "analytics", "communication", "productivity",
    "infrastructure", "security", "UX", "compliance",
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def coerce_enum(value: object, allowed: set[str], default: str = "") -> str:
    """Return *value* if it is a member of *allowed* (case-insensitive).

    Falls back to *default* when the value cannot be matched.
    """
    if not isinstance(value, str):
        return default
    text = value.strip()
    if text in allowed:
        return text
    lowered = text.lower()
    for option in allowed:
        if option.lower() == lowered:
            return option
    return default


def coerce_string_list(
    value: object,
    *,
    allowed: set[str] | None = None,
    max_items: int | None = None,
) -> list[str]:
    """Normalise *value* into a deduplicated list of strings.

    - Strings are split on commas, semicolons, and newlines.
    - Lists are flattened and stripped.
    - When *allowed* is given each item is validated via :func:`coerce_enum`
      and unrecognised items are dropped.
    - *max_items* caps the result length.
    """
    if isinstance(value, str):
        import re as _re
        raw_items = [
            part.strip()
            for part in _re.split(r"[,;\n|]+", value)
            if part.strip()
        ]
    elif isinstance(value, list):
        raw_items = [str(part).strip() for part in value if str(part).strip()]
    else:
        raw_items = []

    seen: set[str] = set()
    items: list[str] = []
    for item in raw_items:
        normalized = item
        if allowed is not None:
            normalized = coerce_enum(item, allowed)
            if not normalized:
                continue
        dedupe_key = normalized.lower()
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        items.append(normalized)
        if max_items is not None and len(items) >= max_items:
            break
    return items
