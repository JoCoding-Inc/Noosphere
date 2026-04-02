from __future__ import annotations

import json
import logging

from backend import llm

logger = logging.getLogger(__name__)


async def detect_domain(input_text: str) -> str:
    """Detect the product domain with specificity.

    Returns a concise domain string like 'AI code-review SaaS' or
    'healthcare compliance automation' rather than a broad category
    such as 'technology' or 'B2B SaaS'.
    """
    prompt = (
        "You are a product analyst. Identify the most specific domain for this product.\n\n"
        "Rules:\n"
        "- Be as specific as possible (3-6 words)\n"
        "- Include the industry vertical AND the product type\n"
        "- Avoid overly broad labels like 'technology', 'SaaS', 'B2B', 'consumer app'\n"
        "- Good examples: 'AI code-review developer tool', 'healthcare compliance automation', "
        "'real-time logistics optimization', 'creator economy monetization platform', "
        "'LLM-powered legal research', 'fintech cross-border payments'\n"
        "- Bad examples: 'technology', 'B2B SaaS', 'developer tools', 'consumer app'\n\n"
        "Return a JSON object with exactly these fields:\n"
        '- "domain": the specific domain string (3-6 words)\n'
        '- "vertical": industry vertical (e.g. healthcare, fintech, devtools, edtech, logistics)\n'
        '- "product_type": what type of product (e.g. automation platform, analytics tool, marketplace)\n\n'
        f"Product description:\n{input_text[:800]}"
    )
    try:
        response = await llm.complete(
            messages=[{"role": "user", "content": prompt}],
            tier="low",
            max_tokens=256,
            response_format={"type": "json_object"},
        )
        data = json.loads(response.content or "{}")
        domain = ""
        if isinstance(data, dict):
            domain = str(data.get("domain", "")).strip().strip('"').strip("'")
            # Fallback: compose from vertical + product_type if domain is too broad
            if domain and len(domain.split()) <= 1:
                vertical = str(data.get("vertical", "")).strip()
                product_type = str(data.get("product_type", "")).strip()
                if vertical and product_type:
                    domain = f"{vertical} {product_type}"
        if not domain:
            # Non-JSON fallback: take first line
            domain = next(iter((response.content or "").strip().splitlines()), "").strip().strip('"').strip("'")
        return domain[:80] or "technology"
    except Exception as exc:
        logger.warning("detect_domain failed: %s", exc)
        return "technology"


async def detect_domain_detailed(input_text: str) -> dict:
    """Return rich domain info: domain, vertical, product_type.

    Unlike ``detect_domain`` which returns a plain string, this variant
    exposes the full structured output so that downstream consumers
    (e.g. persona generation prompts) can leverage vertical and
    product_type independently.
    """
    prompt = (
        "You are a product analyst. Identify the most specific domain for this product.\n\n"
        "Rules:\n"
        "- Be as specific as possible (3-6 words)\n"
        "- Include the industry vertical AND the product type\n"
        "- Avoid overly broad labels like 'technology', 'SaaS', 'B2B', 'consumer app'\n"
        "- Good examples: 'AI code-review developer tool', 'healthcare compliance automation', "
        "'real-time logistics optimization', 'creator economy monetization platform', "
        "'LLM-powered legal research', 'fintech cross-border payments'\n"
        "- Bad examples: 'technology', 'B2B SaaS', 'developer tools', 'consumer app'\n\n"
        "Return a JSON object with exactly these fields:\n"
        '- "domain": the specific domain string (3-6 words)\n'
        '- "vertical": industry vertical (e.g. healthcare, fintech, devtools, edtech, logistics)\n'
        '- "product_type": what type of product (e.g. automation platform, analytics tool, marketplace)\n\n'
        f"Product description:\n{input_text[:800]}"
    )
    try:
        response = await llm.complete(
            messages=[{"role": "user", "content": prompt}],
            tier="low",
            max_tokens=256,
            response_format={"type": "json_object"},
        )
        data = json.loads(response.content or "{}")
        if not isinstance(data, dict):
            data = {}
        domain = str(data.get("domain", "")).strip().strip('"').strip("'")
        vertical = str(data.get("vertical", "")).strip().strip('"').strip("'")
        product_type = str(data.get("product_type", "")).strip().strip('"').strip("'")
        # Fallback: compose from vertical + product_type if domain is too broad
        if domain and len(domain.split()) <= 1 and vertical and product_type:
            domain = f"{vertical} {product_type}"
        return {
            "domain": domain[:80] or "technology",
            "vertical": vertical[:60] or "",
            "product_type": product_type[:60] or "",
        }
    except Exception as exc:
        logger.warning("detect_domain_detailed failed: %s", exc)
        return {"domain": "technology", "vertical": "", "product_type": ""}
