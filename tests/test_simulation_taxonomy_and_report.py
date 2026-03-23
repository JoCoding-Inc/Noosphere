from backend.main import _parse_allowed_origins
from backend.simulation.social_rounds import _render_report_md
from backend.simulation.taxonomy import coerce_enum, coerce_string_list


def _legacy_coerce_enum(value: object, allowed: set[str]) -> str:
    if not isinstance(value, str):
        return ""
    text = value.strip()
    if text in allowed:
        return text
    lowered = text.lower()
    for option in allowed:
        if option.lower() == lowered:
            return option
    return ""


def _legacy_coerce_string_list(
    value: object,
    *,
    allowed: set[str] | None = None,
    max_items: int | None = None,
) -> list[str]:
    if isinstance(value, str):
        raw_items = [
            part.strip()
            for part in value.replace("\n", ",").replace(";", ",").split(",")
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
            normalized = _legacy_coerce_enum(item, allowed)
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


def test_coerce_enum_matches_legacy_behavior() -> None:
    allowed = {"AI/ML", "cloud", "security"}
    samples = ["AI/ML", "ai/ml", " security ", None, 42]

    for sample in samples:
        assert coerce_enum(sample, allowed) == _legacy_coerce_enum(sample, allowed)


def test_coerce_string_list_matches_legacy_behavior() -> None:
    allowed = {"AI/ML", "cloud", "security"}
    samples = [
        "AI/ML; cloud\nsecurity,AI/ML",
        "AI/ML|cloud",
        [" AI/ML ", "cloud", "CLOUD", None],
        None,
    ]

    for sample in samples:
        assert coerce_string_list(sample, allowed=allowed, max_items=3) == _legacy_coerce_string_list(
            sample,
            allowed=allowed,
            max_items=3,
        )


def test_render_report_md_preserves_report_verdict_icons() -> None:
    report = {
        "verdict": "skeptical",
        "evidence_count": 3,
        "segments": [
            {
                "name": "skeptic",
                "sentiment": "negative",
                "summary": "Demand is weak.",
                "key_quotes": ["Not convincing."],
            }
        ],
        "criticism_clusters": [],
        "improvements": [],
    }

    markdown = _render_report_md(report, "Idea", "English")

    assert "## 🤔 Overall Verdict: Skeptical" in markdown
    assert "### 👎 Skeptic" in markdown


def test_parse_allowed_origins_strips_whitespace_and_empty_entries() -> None:
    assert _parse_allowed_origins(" https://a.example , ,https://b.example ") == [
        "https://a.example",
        "https://b.example",
    ]
    assert _parse_allowed_origins("") == ["*"]
