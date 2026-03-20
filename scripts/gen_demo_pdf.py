#!/usr/bin/env python3
"""
데모용 PDF를 미리 생성해 frontend/public/noosphere-demo-report.pdf 에 저장합니다.

사용법:
    python scripts/gen_demo_pdf.py

의존: typst CLI가 PATH에 있어야 합니다.
"""
import asyncio
import sys
from pathlib import Path

# 프로젝트 루트를 sys.path에 추가
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from backend.exporter import build_pdf  # noqa: E402

DEMO_INPUT = """\
Noosphere is an AI-powered market simulator that predicts real-world reactions \
to your product before you launch.

Paste your landing page, pitch deck, or product description and Noosphere will:
- Collect context from GitHub, arXiv, Hacker News, Reddit, and more
- Generate 50+ AI personas representing your target audience
- Run multi-round social simulations across 5 tech platforms
- Deliver a structured analysis: verdict, sentiment by segment, key criticisms, \
and improvement suggestions

Built for founders, PMs, and product teams who want signal before noise.\
"""

ANALYSIS_MD = """\
## Market Analysis — Noosphere

**Domain:** AI / Developer Tools · SaaS

### Executive Summary

Noosphere enters a nascent but rapidly growing category of AI-driven market intelligence tools. \
The concept of simulating social reactions before launch resonates strongly with founders and \
product managers who have experienced costly positioning mistakes post-launch.

---

### Community Reception Overview

Across all five simulated platforms, the overall reception was **cautiously optimistic**. \
Technical communities (Hacker News, r/startups) exhibited healthy skepticism around simulation \
fidelity, while practitioner communities (Product Hunt, Indie Hackers, LinkedIn) responded with \
clear enthusiasm.

**Hacker News** — High engagement with critical undertones. The HN community praised the \
technical ambition but pushed back on whether LLM-based simulations can accurately model \
community-specific culture and bias. The "AI wrapper" concern surfaced but was partially offset \
by the depth of the multi-agent architecture.

**Product Hunt** — Strong positive response. Practitioners resonated with the pain point \
immediately. The "launch validation" framing is compelling to this audience. Expected to perform \
well on launch day.

**Indie Hackers** — Highly favorable. Indie hackers are acutely aware of the cost of misaligned \
positioning. The product's ability to simulate Reddit and HN reactions is a direct address of \
their core anxiety.

**Reddit r/startups** — Mixed. Some users were skeptical of AI-generated feedback as a \
substitute for real customer conversations. Others saw it as a complement to, not replacement \
for, traditional validation.

**LinkedIn** — Positive and professional. GTM teams and PMs responded well to the structured \
output (verdict + segments + improvements). The corporate framing around "reducing go-to-market \
uncertainty" landed effectively.

---

### Key Signals

- The "before you launch" positioning is the strongest hook across all communities
- Multi-platform coverage (not just one community) is a significant differentiator
- The word "simulate" triggers skepticism in technical communities — consider "predict" or "model"
- Persona diversity and methodology transparency will be important for trust-building

---

### Recommended Actions

1. **Lead with outcomes, not mechanics** — Frame results as "here's what HN will say" not \
"here's how our agents work"
2. **Publish a methodology doc** — Technical communities want to audit the simulation approach
3. **Add a confidence score** — Helps users calibrate how much to rely on results
4. **Community-specific tuning** — Show that you understand each platform's culture, not just \
aggregate sentiment\
"""

REPORT_MD = """\
## Verdict: MIXED

Based on **127** simulated interactions.

## Segment Reactions

### 😐 Hacker News

High engagement with critical undertones. Strong interest in methodology and simulation fidelity. \
"AI wrapper" concern raised but countered by depth of implementation.

> "Interesting concept. The biggest risk I see is that simulated reactions might not capture \
the nuance of actual HN culture — we're famously unpredictable."

> "The technical implementation here is more interesting than the product surface suggests. \
LLM-based agent simulation with network effects modeled in?"

> "Another AI wrapper? Show me the methodology."

### 👍 Product Hunt

Practitioners immediately connected with the pain point. Strong upvote potential. \
"Launch validation" framing resonates powerfully with this audience.

> "This is exactly what I needed before my last launch. Would have saved me weeks of \
misaligned positioning."

> "🚀 Day 1 upvote. The persona diversity feels surprisingly real."

### 👍 Indie Hackers

Highly favorable reception. IH users acutely aware of positioning risk. Multiple users \
reported plans to test on their own products immediately.

> "Just tried this on my SaaS landing page. The Reddit simulation was surprisingly accurate \
— called out my vague value prop immediately."

> "Running this on my B2B SaaS tonight. Will report back."

### 😐 Reddit r/startups

Mixed reception with constructive skepticism. Community values real customer feedback over \
AI simulation but sees potential as a complement.

> "From an investment standpoint, tools that reduce go-to-market uncertainty are always \
interesting. The question is repeatability."

> "One good simulation doesn't make a moat."

### 👍 LinkedIn

Professional audience responded well to structured output and GTM framing. PMs and GTM leaders \
see clear workflow integration.

> "As a PM, the ability to stress-test messaging across different communities before launch \
is massive."

> "The LinkedIn simulation is uncannily accurate — right down to the corporate buzzword patterns."

---

## Criticism Patterns

**Simulation fidelity concerns** (23 mentions)
- Can AI truly capture community-specific culture and bias?
- Simulated personas may not reflect real edge cases and outliers
- HN culture is famously hard to predict — even for humans

**AI wrapper skepticism** (17 mentions)
- "Another AI wrapper" sentiment from technical users
- Questions about defensibility and moat
- Concerns about prompt engineering quality

**Methodology transparency** (14 mentions)
- No published methodology for simulation approach
- Unclear how agent personas are calibrated
- Want to see validation against real launch outcomes

---

## Improvement Suggestions

1. Publish a detailed methodology document explaining agent design and simulation approach _(×31)_
2. Add confidence scores or uncertainty ranges to simulation outputs _(×24)_
3. Include a "real vs. simulated" accuracy case study from a past launch _(×19)_
4. Allow users to customize persona demographics and technical backgrounds _(×15)_
5. Add integration with existing tools (Notion, Loom, Figma) for frictionless input _(×11)_\
"""


async def main() -> None:
    out_path = ROOT / "frontend" / "public" / "noosphere-demo-report.pdf"
    print("PDF 생성 중...")
    pdf_bytes = await build_pdf(
        report_md=REPORT_MD,
        input_text=DEMO_INPUT,
        sim_id="demo",
        domain="AI / Developer Tools",
        language="English",
        analysis_md=ANALYSIS_MD,
    )
    out_path.write_bytes(pdf_bytes)
    print(f"저장 완료: {out_path}  ({len(pdf_bytes):,} bytes)")


if __name__ == "__main__":
    asyncio.run(main())
