import { useEffect, useState } from 'react'
import { MOCK_SOURCES, MOCK_PERSONAS, MOCK_POSTS } from '../hooks/useMockSimulation'
import { SOURCE_COLORS, PLATFORM_COLORS, PLATFORM_OPTIONS } from '../constants'
import { t } from '../tokens'
import { ReportView } from './ReportView'
import { MarkdownView } from './MarkdownView'
import { PlatformSimFeed } from './PlatformSimFeed'
import { DetailsView } from './DetailsView'
import { ContextGraph } from './OntologyGraph'
import type { Platform, SocialPost, SimResults, ContextGraphData } from '../types'

// ── Mock context graph (collected document graph) ─────────────────────────────

const MOCK_GRAPH_DATA: ContextGraphData = {
  nodes: [
    { id: 's1', title: 'microsoft/autogen — Multi-Agent Framework',                   source: 'github',           url: 'https://github.com/microsoft/autogen' },
    { id: 's2', title: 'LLM-based Multi-Agent Systems for Social Simulation',          source: 'arxiv',            url: 'https://arxiv.org/abs/2312.01234' },
    { id: 's3', title: 'Ask HN: How do you validate product ideas before building?',   source: 'hackernews',       url: 'https://news.ycombinator.com/item?id=1' },
    { id: 's4', title: 'stanfordnlp/dspy — Programming Foundation Models',             source: 'github',           url: 'https://github.com/stanfordnlp/dspy' },
    { id: 's5', title: 'Generative Agents: Interactive Simulacra of Human Behavior',   source: 'arxiv',            url: 'https://arxiv.org/abs/2304.03442' },
    { id: 's6', title: 'r/startups: What tools do you use for pre-launch validation?', source: 'reddit',           url: 'https://reddit.com/r/startups' },
    { id: 's7', title: 'Top AI-powered research tools of 2024',                        source: 'product_hunt',     url: 'https://producthunt.com' },
    { id: 's8', title: 'AgentSims: An Open-Source Sandbox for LLM Agent Evaluation',  source: 'arxiv',            url: 'https://arxiv.org/abs/2308.04026' },
    { id: 's9', title: 'Attention Is All You Need',                                    source: 'arxiv',            url: 'https://arxiv.org/abs/1706.03762' },
    { id: 's10', title: 'Show HN: I built a tool to simulate social media reactions', source: 'hackernews',       url: 'https://news.ycombinator.com' },
  ],
  edges: [
    { source: 's1', target: 's2', weight: 6, label: 'multi-agent · simulation' },
    { source: 's1', target: 's4', weight: 4, label: 'LLM · framework' },
    { source: 's2', target: 's5', weight: 7, label: 'agent simulation · social' },
    { source: 's2', target: 's8', weight: 5, label: 'LLM agents · evaluation' },
    { source: 's3', target: 's6', weight: 4, label: 'validation · startup' },
    { source: 's3', target: 's10', weight: 5, label: 'HN · product validation' },
    { source: 's5', target: 's8', weight: 6, label: 'generative agents · simulation' },
    { source: 's5', target: 's9', weight: 4, label: 'transformer · attention' },
    { source: 's4', target: 's9', weight: 3, label: 'language model' },
    { source: 's6', target: 's7', weight: 3, label: 'product · market' },
    { source: 's7', target: 's10', weight: 4, label: 'product launch · community' },
  ],
}

// ── Mock results (extracted from DemoPage) ───────────────────────────────────

const MOCK_RESULTS: SimResults = {
  sim_id: 'demo',
  analysis_md: `## Market Analysis — Noosphere

**Domain:** AI / Developer Tools · SaaS

### Executive Summary

Noosphere enters a nascent but rapidly growing category of AI-driven market intelligence tools. The concept of simulating social reactions before launch resonates strongly with founders and product managers who have experienced costly positioning mistakes post-launch.

---

### Community Reception Overview

Across all five simulated platforms, the overall reception was **cautiously optimistic**. Technical communities (Hacker News, r/startups) exhibited healthy skepticism around simulation fidelity, while practitioner communities (Product Hunt, Indie Hackers, LinkedIn) responded with clear enthusiasm.

**Hacker News** — High engagement with critical undertones. The HN community praised the technical ambition but pushed back on whether LLM-based simulations can accurately model community-specific culture and bias. The "AI wrapper" concern surfaced but was partially offset by the depth of the multi-agent architecture.

**Product Hunt** — Strong positive response. Practitioners resonated with the pain point immediately. The "launch validation" framing is compelling to this audience. Expected to perform well on launch day.

**Indie Hackers** — Highly favorable. Indie hackers are acutely aware of the cost of misaligned positioning. The product's ability to simulate Reddit and HN reactions is a direct address of their core anxiety.

**Reddit r/startups** — Mixed. Some users were skeptical of AI-generated feedback as a substitute for real customer conversations. Others saw it as a complement to, not replacement for, traditional validation.

**LinkedIn** — Positive and professional. GTM teams and PMs responded well to the structured output (verdict + segments + improvements). The corporate framing around "reducing go-to-market uncertainty" landed effectively.

---

### Key Signals

- The "before you launch" positioning is the strongest hook across all communities
- Multi-platform coverage (not just one community) is a significant differentiator
- The word "simulate" triggers skepticism in technical communities — consider "predict" or "model"
- Persona diversity and methodology transparency will be important for trust-building

---

### Recommended Actions

1. **Lead with outcomes, not mechanics** — Frame results as "here's what HN will say" not "here's how our agents work"
2. **Publish a methodology doc** — Technical communities want to audit the simulation approach
3. **Add a confidence score** — Helps users calibrate how much to rely on results
4. **Community-specific tuning** — Show that you understand each platform's culture, not just aggregate sentiment`,

  report_json: {
    verdict: 'mixed',
    evidence_count: 127,
    segments: [
      {
        name: 'Hacker News',
        sentiment: 'neutral',
        summary: 'Technical community engaged but skeptical. Strong interest in methodology and simulation fidelity. "AI wrapper" concern raised but countered by depth of implementation.',
        key_quotes: [
          '"Interesting concept. The biggest risk I see is that simulated reactions might not capture the nuance of actual HN culture — we\'re famously unpredictable."',
          '"The technical implementation here is more interesting than the product surface suggests. LLM-based agent simulation with network effects modeled in?"',
          '"Another AI wrapper? Show me the methodology."',
        ],
      },
      {
        name: 'Product Hunt',
        sentiment: 'positive',
        summary: 'Practitioners immediately connected with the pain point. Strong upvote potential. "Launch validation" framing resonates powerfully with this audience.',
        key_quotes: [
          '"This is exactly what I needed before my last launch. Would have saved me weeks of misaligned positioning."',
          '"🚀 Day 1 upvote. The persona diversity feels surprisingly real."',
          '"Finally a tool that answers the question I ask before every launch."',
        ],
      },
      {
        name: 'Indie Hackers',
        sentiment: 'positive',
        summary: 'Highly favorable reception. IH users acutely aware of positioning risk. Multiple users reported plans to test on their own products immediately.',
        key_quotes: [
          '"Just tried this on my SaaS landing page. The Reddit simulation was surprisingly accurate — called out my vague value prop immediately."',
          '"Does this work for non-technical products? I build no-code tools and my users are not developers."',
          '"Running this on my B2B SaaS tonight. Will report back."',
        ],
      },
      {
        name: 'Reddit r/startups',
        sentiment: 'neutral',
        summary: 'Mixed reception with constructive skepticism. Community values real customer feedback over AI simulation but sees potential as a complement.',
        key_quotes: [
          '"From an investment standpoint, tools that reduce go-to-market uncertainty are always interesting. The question is repeatability."',
          '"One good simulation doesn\'t make a moat."',
          '"Interesting but I\'d still rather talk to 10 real customers."',
        ],
      },
      {
        name: 'LinkedIn',
        sentiment: 'positive',
        summary: 'Professional audience responded well to structured output and GTM framing. PMs and GTM leaders see clear workflow integration.',
        key_quotes: [
          '"As a PM, the ability to stress-test messaging across different communities before launch is massive."',
          '"The LinkedIn simulation is uncannily accurate — right down to the corporate buzzword patterns."',
          '"Shared this with our GTM team. Everyone immediately saw the use case."',
        ],
      },
    ],
    criticism_clusters: [
      {
        theme: 'Simulation fidelity concerns',
        count: 23,
        examples: [
          'Can AI truly capture community-specific culture and bias?',
          'Simulated personas may not reflect real edge cases and outliers',
          'HN culture is famously hard to predict — even for humans',
        ],
      },
      {
        theme: 'AI wrapper skepticism',
        count: 17,
        examples: [
          '"Another AI wrapper" sentiment from technical users',
          'Questions about defensibility and moat',
          'Concerns about prompt engineering quality',
        ],
      },
      {
        theme: 'Methodology transparency',
        count: 14,
        examples: [
          'No published methodology for simulation approach',
          'Unclear how agent personas are calibrated',
          'Want to see validation against real launch outcomes',
        ],
      },
    ],
    improvements: [
      { suggestion: 'Publish a detailed methodology document explaining agent design and simulation approach', frequency: 31 },
      { suggestion: 'Add confidence scores or uncertainty ranges to simulation outputs', frequency: 24 },
      { suggestion: 'Include a "real vs. simulated" accuracy case study from a past launch', frequency: 19 },
      { suggestion: 'Allow users to customize persona demographics and technical backgrounds', frequency: 15 },
      { suggestion: 'Add integration with existing tools (Notion, Loom, Figma) for frictionless input', frequency: 11 },
    ],
  },

  posts_json: {
    hackernews: [
      { id: 'r-hn-1', platform: 'hackernews', author_node_id: 'n1', author_name: 'Marcus Chen', content: 'Interesting concept. The biggest risk I see is that simulated reactions might not capture the nuance of actual HN culture — we\'re famously unpredictable. That said, for early validation this could be genuinely useful.', action_type: 'comment', round_num: 1, upvotes: 67, downvotes: 2, parent_id: null },
      { id: 'r-hn-2', platform: 'hackernews', author_node_id: 'n5', author_name: 'TechSkeptic99', content: 'Another AI wrapper? The real question is how accurately it models different community subcultures. Reddit r/startups vs HN have very different signal-to-noise ratios. Show me the methodology.', action_type: 'comment', round_num: 1, upvotes: 43, downvotes: 1, parent_id: null },
      { id: 'r-hn-3', platform: 'hackernews', author_node_id: 'n9', author_name: 'rachel_cto', content: 'The technical implementation here is more interesting than the product surface suggests. LLM-based agent simulation with network effects modeled in? Someone did their homework on social dynamics research.', action_type: 'comment', round_num: 2, upvotes: 89, downvotes: 0, parent_id: null },
    ],
    producthunt: [
      { id: 'r-ph-1', platform: 'producthunt', author_node_id: 'n6', author_name: 'priya_builds', content: '🚀 This is exactly what I needed before my last launch. Would have saved me weeks of misaligned positioning. Upvoted!', action_type: 'review', round_num: 1, upvotes: 54, downvotes: 0, parent_id: null },
    ],
    indiehackers: [
      { id: 'r-ih-1', platform: 'indiehackers', author_node_id: 'n3', author_name: 'devdave42', content: 'Just tried this on my SaaS landing page. The Reddit simulation was surprisingly accurate — called out my vague value prop immediately. Highly recommend running this before you ship.', action_type: 'post', round_num: 1, upvotes: 38, downvotes: 0, parent_id: null },
      { id: 'r-ih-2', platform: 'indiehackers', author_node_id: 'n8', author_name: 'nocodeNate', content: 'Does this work for non-technical products? I build no-code tools and my users are not developers. Curious if the personas can capture that audience accurately.', action_type: 'comment', round_num: 2, upvotes: 21, downvotes: 0, parent_id: null },
    ],
    reddit_startups: [
      { id: 'r-rs-1', platform: 'reddit_startups', author_node_id: 'n4', author_name: 'VentureVC_Alex', content: 'From an investment standpoint, tools that reduce go-to-market uncertainty are always interesting. The question is repeatability. One good simulation doesn\'t make a moat.', action_type: 'comment', round_num: 1, upvotes: 29, downvotes: 3, parent_id: null },
      { id: 'r-rs-2', platform: 'reddit_startups', author_node_id: 'n10', author_name: 'bootstrapped_bo', content: 'Running this on my B2B SaaS tonight. Will report back. The free tier seems generous for what you get. Anyone else tried it on enterprise positioning?', action_type: 'post', round_num: 2, upvotes: 17, downvotes: 1, parent_id: null },
    ],
    linkedin: [
      { id: 'r-li-1', platform: 'linkedin', author_node_id: 'n2', author_name: 'Sarah K.', content: 'Just discovered Noosphere and I\'m genuinely impressed. As a PM, the ability to stress-test messaging across different communities before launch is massive. The persona diversity feels real.', action_type: 'post', round_num: 1, upvotes: 76, downvotes: 0, parent_id: null },
      { id: 'r-li-2', platform: 'linkedin', author_node_id: 'n7', author_name: 'james_pm', content: 'Shared this with our GTM team. The LinkedIn simulation is uncannily accurate — right down to the corporate buzzword patterns. 😄 Solid product.', action_type: 'comment', round_num: 2, upvotes: 61, downvotes: 0, parent_id: null },
    ],
  },

  personas_json: {
    hackernews: [
      { node_id: 'n1', name: 'Marcus Chen', role: 'Senior Software Engineer', mbti: 'INTJ', bias: 'technically rigorous, skeptical of hype', interests: ['distributed systems', 'Rust', 'open source'] },
      { node_id: 'n5', name: 'TechSkeptic99', role: 'Staff Engineer', mbti: 'INTP', bias: 'contrarian, methodology-focused', interests: ['compilers', 'formal verification', 'benchmarking'] },
      { node_id: 'n9', name: 'rachel_cto', role: 'CTO', mbti: 'ENTJ', bias: 'pragmatic, research-aware', interests: ['AI research', 'system design', 'team building'] },
    ],
    producthunt: [
      { node_id: 'n6', name: 'priya_builds', role: 'Founder', mbti: 'ENFJ', bias: 'optimistic early adopter', interests: ['SaaS', 'no-code', 'community building'] },
    ],
    indiehackers: [
      { node_id: 'n3', name: 'devdave42', role: 'Indie Hacker', mbti: 'ISTP', bias: 'pragmatic, ROI-focused', interests: ['bootstrapping', 'Laravel', 'MRR optimization'] },
      { node_id: 'n8', name: 'nocodeNate', role: 'No-code builder', mbti: 'ESFP', bias: 'accessibility-focused, non-technical', interests: ['Bubble', 'Zapier', 'solopreneurship'] },
    ],
    reddit_startups: [
      { node_id: 'n4', name: 'VentureVC_Alex', role: 'VC Analyst', mbti: 'ESTJ', bias: 'investment return focused', interests: ['market sizing', 'defensibility', 'unit economics'] },
      { node_id: 'n10', name: 'bootstrapped_bo', role: 'Bootstrapped founder', mbti: 'ISTJ', bias: 'cost-conscious, self-reliant', interests: ['B2B SaaS', 'cold outreach', 'churn reduction'] },
    ],
    linkedin: [
      { node_id: 'n2', name: 'Sarah K.', role: 'Product Manager', mbti: 'ENFP', bias: 'user empathy, cross-functional', interests: ['product strategy', 'user research', 'OKRs'] },
      { node_id: 'n7', name: 'james_pm', role: 'Head of Product', mbti: 'ENTJ', bias: 'GTM execution', interests: ['positioning', 'sales enablement', 'roadmapping'] },
    ],
  },
  report_md: '',
  context_nodes_json: MOCK_GRAPH_DATA.nodes,
  sources_json: [
    { id: 's1', source: 'github',           title: 'microsoft/autogen — Multi-Agent Framework',                          score: 0.91, url: 'https://github.com/microsoft/autogen',     date: '2024-11' },
    { id: 's2', source: 'arxiv',            title: 'LLM-based Multi-Agent Systems for Social Simulation',                score: 0.88, url: 'https://arxiv.org/abs/2312.01234',          date: '2024-09' },
    { id: 's3', source: 'hackernews',       title: 'Ask HN: How do you validate product ideas before building?',         score: 0.85, url: 'https://news.ycombinator.com/item?id=1',   date: '2024-10' },
    { id: 's4', source: 'github',           title: 'stanfordnlp/dspy — Programming Foundation Models',                   score: 0.82, url: 'https://github.com/stanfordnlp/dspy',       date: '2024-12' },
    { id: 's5', source: 'semantic_scholar', title: 'Generative Agents: Interactive Simulacra of Human Behavior',         score: 0.80, url: 'https://arxiv.org/abs/2304.03442',          date: '2023-04' },
    { id: 's6', source: 'reddit',           title: 'r/startups: What tools do you use for pre-launch market validation?', score: 0.78, url: 'https://reddit.com/r/startups',             date: '2024-11' },
    { id: 's7', source: 'product_hunt',     title: 'Top AI-powered research tools of 2024',                              score: 0.74, url: 'https://producthunt.com',                    date: '2024-12' },
    { id: 's8', source: 'arxiv',            title: 'AgentSims: An Open-Source Sandbox for LLM Agent Evaluation',        score: 0.71, url: 'https://arxiv.org/abs/2308.04026',          date: '2023-08' },
  ],
  final_report_md: `## Final Report — Noosphere

### Overall Verdict: Mixed ⚖️

The simulation of 127 interactions across 5 platforms reveals a product with strong practitioner-market fit and genuine technical ambition, tempered by recurring skepticism from highly technical audiences.

---

### Platform-by-Platform Summary

**Hacker News** — Cautiously skeptical. The community engaged with depth but consistently pushed back on simulation fidelity and methodology opacity. Expect a polarised thread: enthusiasts vs. skeptics.

**Product Hunt** — High potential. Clear resonance with the core value proposition. Expect strong Day 1 upvotes from founders who have experienced positioning failures.

**Indie Hackers** — Strongest reception. Direct alignment with IH community pain points around pre-launch validation. High likelihood of organic word-of-mouth.

**Reddit r/startups** — Mixed. Community values real customer conversations; simulation perceived as complement rather than replacement. Constructive tone overall.

**LinkedIn** — Positive and professional. GTM and product audiences connected with structured output format.

---

### Top 3 Actions

1. **Publish methodology** — transparency document for technical audiences
2. **Add confidence indicators** — help users calibrate reliance on results
3. **Reframe "simulate" → "predict"** — reduces friction with skeptical communities`,
  gtm_md: '',
}

// ── Demo config constants ─────────────────────────────────────────────────────

const DEMO_INPUT = `Noosphere is an AI-powered market simulator that predicts real-world reactions to your product before you launch.

Paste your landing page, pitch deck, or product description and Noosphere will:
- Collect context from GitHub, arXiv, Hacker News, Reddit, and more
- Generate 50+ AI personas representing your target audience
- Run multi-round social simulations across 5 tech platforms
- Deliver a structured analysis: verdict, sentiment by segment, key criticisms`

type Phase = 'home' | 'simulate' | 'results'
type ResultTab = 'analysis' | 'simulation' | 'final' | 'details'

// ── Sub-components (display-only, no event handlers) ─────────────────────────

function HomePhase({ displayText, runClicked }: { displayText: string; runClicked: boolean }) {
  return (
    <div style={{ background: t.color.bgCard, height: '100%', overflowY: 'hidden' }}>
      <div style={{ padding: `${t.space[8]} ${t.space[6]} ${t.space[6]}` }}>
        <div style={{ marginBottom: t.space[6] }}>
          <h1 style={{ fontSize: 34, fontWeight: 800, letterSpacing: '-0.04em', margin: `0 0 ${t.space[2]}`, color: t.color.textPrimary }}>
            How will the market react?
          </h1>
          <p style={{ color: t.color.textSecondary, fontSize: 15, margin: 0 }}>
            Describe your product and simulate real-world reactions across tech communities.
          </p>
        </div>

        <div style={{
          width: '100%', padding: '16px 18px',
          fontSize: 15,
          border: `1.5px solid ${displayText.length < DEMO_INPUT.length ? '#8b5cf6' : t.color.border}`,
          borderRadius: t.radius.lg, background: t.color.bgPage,
          fontFamily: 'inherit', lineHeight: 1.6,
          color: t.color.textPrimary,
          boxShadow: displayText.length < DEMO_INPUT.length ? '0 0 0 3px rgba(139,92,246,0.12)' : 'none',
          minHeight: 168, whiteSpace: 'pre-wrap',
          wordBreak: 'break-word',
          boxSizing: 'border-box' as const,
        }}>
          {displayText}
          {displayText.length < DEMO_INPUT.length && (
            <span className="cursor-blink" style={{ display: 'inline' }} />
          )}
        </div>

        <div style={{ marginTop: t.space[4], display: 'flex', gap: t.space[2], flexWrap: 'wrap' }}>
          {PLATFORM_OPTIONS.map(p => (
            <span key={p.id} style={{
              display: 'inline-flex', alignItems: 'center', gap: t.space[1],
              padding: '7px 14px', fontSize: t.font.size.md, borderRadius: t.radius.md,
              border: `1.5px solid ${t.color.textPrimary}`,
              background: t.color.textPrimary, color: t.color.textInverse, fontWeight: t.font.weight.semibold,
              boxShadow: '0 2px 8px rgba(30,41,59,0.25)',
            }}>
              {p.label}
            </span>
          ))}
        </div>

        <div style={{ marginTop: t.space[5] }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: t.space[1], color: t.color.textSecondary, fontSize: t.font.size.md }}>
            <span>▶</span>
            Advanced options
            <span style={{
              fontSize: t.font.size.xs, padding: '2px 8px', borderRadius: t.radius.lg,
              background: t.color.bgSubtle, color: t.color.textMuted, marginLeft: t.space[1],
            }}>
              English · 12r · 50a · ~470 sources
            </span>
          </div>
        </div>

        <div style={{
          marginTop: t.space[5],
          padding: `${t.space[3]} ${t.space[8]}`, fontSize: 15, fontWeight: t.font.weight.bold,
          background: t.color.textPrimary, color: t.color.textInverse,
          borderRadius: t.radius.lg, display: 'inline-block',
          letterSpacing: '-0.01em',
          animation: runClicked ? 'runClick 200ms ease forwards' : 'none',
        }}>
          Run Simulation →
        </div>
      </div>
    </div>
  )
}

function SimulatePhase({
  sources, personaCount, personaPct, posts, simRound, graphData, activePlatform,
}: {
  sources: typeof MOCK_SOURCES
  personaCount: number
  personaPct: number
  posts: SocialPost[]
  simRound: number
  graphData: ContextGraphData | null
  activePlatform?: Platform
}) {
  const showSources  = sources.length > 0
  const showPersonas = sources.length === 0 && personaCount > 0 && simRound === 0
  const showPosts    = simRound > 0

  // Group posts by platform for PlatformSimFeed
  const postsByPlatform = posts.reduce((acc, post) => {
    if (!acc[post.platform]) acc[post.platform] = []
    acc[post.platform]!.push(post)
    return acc
  }, {} as Partial<Record<Platform, SocialPost[]>>)

  const activePlatforms = Object.keys(postsByPlatform) as Platform[]
  const totalPosts = posts.length

  const phaseLabel = showSources
    ? 'Searching sources...'
    : showPersonas
    ? `Generating personas — ${personaCount} / ${MOCK_PERSONAS.length}`
    : showPosts
    ? `Round ${simRound} · ${totalPosts} posts`
    : 'Initializing...'

  // 피드 패널 (헤더 + 소스/페르소나/포스트)
  const feedPanel = (
    <>
      {/* Phase header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: t.space[3], marginBottom: t.space[2] }}>
        <span style={{
          display: 'inline-block', width: 10, height: 10, borderRadius: '50%',
          background: t.color.success, flexShrink: 0,
          animation: 'pulse 1.5s infinite',
        }} />
        <h2 style={{ margin: 0, fontSize: t.font.size['2xl'], fontWeight: t.font.weight.bold, letterSpacing: '-0.02em' }}>
          {phaseLabel}
        </h2>
      </div>

      {/* Persona progress bar */}
      {showPersonas && (
        <div style={{ margin: `0 0 ${t.space[6]} 0` }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: t.font.size.sm, color: t.color.textMuted, marginBottom: t.space[1] }}>
            <span>Building agent personas</span>
            <span>{personaCount} / {MOCK_PERSONAS.length}</span>
          </div>
          <div style={{ height: 6, background: t.color.border, borderRadius: 3, overflow: 'hidden' }}>
            <div style={{
              height: '100%', borderRadius: 3,
              background: 'linear-gradient(90deg, #8b5cf6, #6366f1)',
              width: `${personaPct}%`,
              transition: 'width 0.4s ease',
              boxShadow: '0 0 8px rgba(139,92,246,0.5)',
            }} />
          </div>
        </div>
      )}

      {/* Source timeline */}
      {showSources && (
        <div style={{ marginBottom: t.space[5] }}>
          <div style={{ fontSize: t.font.size.xs, color: t.color.textMuted, marginBottom: t.space[2] }}>
            {sources.length} items collected
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: t.space[1] }}>
            {sources.map((src, i) => (
              <div key={i} className="source-item" style={{
                padding: '8px 12px', borderRadius: t.radius.md,
                background: t.color.bgPage, border: `1px solid ${t.color.border}`,
                borderLeft: `3px solid ${SOURCE_COLORS[src.source] || t.color.textMuted}`,
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: t.space[1], marginBottom: t.space[1] }}>
                  <span style={{
                    fontSize: t.font.size.xs, fontWeight: t.font.weight.bold, padding: '1px 6px', borderRadius: t.radius.md,
                    background: `${SOURCE_COLORS[src.source] || t.color.textMuted}18`,
                    color: SOURCE_COLORS[src.source] || t.color.textSecondary,
                    textTransform: 'uppercase', letterSpacing: '0.04em',
                  }}>
                    {src.source}
                  </span>
                </div>
                <div style={{ fontSize: t.font.size.md, fontWeight: t.font.weight.semibold, color: t.color.textPrimary, lineHeight: 1.4 }}>
                  {src.title}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Platform counters */}
      {showPosts && activePlatforms.length > 0 && (
        <div style={{ display: 'flex', gap: t.space[2], flexWrap: 'wrap', marginBottom: t.space[4] }}>
          {activePlatforms.map(platform => (
            <span key={platform} style={{
              fontSize: t.font.size.sm, padding: '4px 10px', borderRadius: t.radius.pill,
              background: t.color.bgSubtle, color: '#475569',
              display: 'flex', alignItems: 'center', gap: t.space[1],
            }}>
              <span style={{
                width: 7, height: 7, borderRadius: '50%', flexShrink: 0,
                background: PLATFORM_COLORS[platform] || t.color.textMuted,
              }} />
              {platform.replace('_', ' ')} · {postsByPlatform[platform]?.length ?? 0}
            </span>
          ))}
        </div>
      )}

      {/* PlatformSimFeed */}
      {showPosts && totalPosts > 0 && (
        <div style={{ borderTop: `1px solid ${t.color.border}`, paddingTop: t.space[4] }}>
          <PlatformSimFeed postsByPlatform={postsByPlatform} ideaText="Noosphere – AI market simulator" forcedTab={activePlatform} />
        </div>
      )}
    </>
  )

  return (
    <div style={{ background: t.color.bgCard, height: '100%', overflowY: 'hidden' }}>
      {(showSources && graphData) ? (
        /* 소싱 단계: 왼쪽 그래프 + 오른쪽 소스 타임라인 */
        <div style={{
          width: '100%', padding: `${t.space[8]} ${t.space[6]}`,
          display: 'flex', gap: t.space[6], alignItems: 'flex-start',
          boxSizing: 'border-box',
        }}>
          <div style={{ width: 360, flexShrink: 0, minWidth: 0, animation: 'fadeInUp 0.4s ease' }}>
            <p style={{ fontSize: t.font.size.xs, fontWeight: t.font.weight.bold, color: t.color.textMuted, letterSpacing: '0.06em', textTransform: 'uppercase', margin: `0 0 ${t.space[2]}` }}>
              Knowledge Graph
            </p>
            <ContextGraph data={graphData} width={360} />
          </div>
          <div style={{ flex: 1, minWidth: 0, paddingTop: 4 }}>
            {feedPanel}
          </div>
        </div>
      ) : (
        /* 소싱 이후: 1컬럼 */
        <div style={{ padding: `${t.space[8]} ${t.space[6]} ${t.space[5]}` }}>
          {feedPanel}
        </div>
      )}
    </div>
  )
}

function ResultsPhase({ tab, detailTab }: { tab: ResultTab; detailTab: 'feed' | 'personas' }) {
  const tabs: { id: ResultTab; label: string }[] = [
    { id: 'analysis',   label: 'Analysis' },
    { id: 'simulation', label: 'Simulation' },
    { id: 'final',      label: 'Final Report' },
    { id: 'details',    label: 'Details' },
  ]

  return (
    <div style={{ background: t.color.bgBody, height: '100%', display: 'flex', flexDirection: 'column' }}>
      {/* Top bar — exact DemoResultView / ResultPage style */}
      <div style={{ width: '100%', padding: `${t.space[6]} ${t.space[6]} 0`, flexShrink: 0 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: t.space[4] }}>
          <div style={{ color: t.color.textSecondary, fontSize: t.font.size.lg }}>← Run demo again</div>
          <div style={{
            fontSize: t.font.size.sm, padding: '4px 12px', borderRadius: t.radius.pill,
            background: 'rgba(139,92,246,0.1)', color: '#8b5cf6', fontWeight: t.font.weight.semibold,
          }}>
            Demo Results
          </div>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: `1px solid ${t.color.border}` }}>
          <div style={{ display: 'flex', gap: t.space[1] }}>
            {tabs.map(tabItem => (
              <div key={tabItem.id} style={{
                padding: '10px 20px', fontSize: t.font.size.lg, cursor: 'default',
                fontWeight: tab === tabItem.id ? t.font.weight.semibold : t.font.weight.normal,
                borderBottom: tab === tabItem.id ? `2px solid ${t.color.textPrimary}` : '2px solid transparent',
                color: tab === tabItem.id ? t.color.textPrimary : t.color.textSecondary,
                transition: 'color 0.15s, border-color 0.15s',
              }}>
                {tabItem.label}
              </div>
            ))}
          </div>
          <div style={{
            display: 'inline-block', padding: '8px 18px', background: t.color.textPrimary,
            color: t.color.textInverse, borderRadius: t.radius.md, fontSize: t.font.size.md, fontWeight: t.font.weight.semibold, marginBottom: t.space[1],
          }}>
            ↓ Download Report
          </div>
        </div>
      </div>

      {/* Tab content — uses same components as DemoResultView */}
      <div key={tab} className="tab-content" style={{ flex: 1, overflow: 'hidden', padding: `0 ${t.space[6]}` }}>
        {tab === 'analysis' && (
          <div>
            <MarkdownView content={MOCK_RESULTS.analysis_md} />
            <div style={{ marginTop: t.space[8] }}>
              <div style={{
                display: 'flex', alignItems: 'center', gap: t.space[1],
                background: 'none', border: `1px solid ${t.color.border}`, borderRadius: 7,
                padding: '7px 14px', fontSize: t.font.size.md, color: t.color.textSecondary, width: 'fit-content',
              }}>
                ▸ Sources ({MOCK_RESULTS.sources_json.length})
              </div>
            </div>
          </div>
        )}
        {tab === 'simulation' && (
          <ReportView report={MOCK_RESULTS.report_json} />
        )}
        {tab === 'final' && (
          <MarkdownView content={MOCK_RESULTS.final_report_md} />
        )}
        {tab === 'details' && (
          <DetailsView posts={MOCK_RESULTS.posts_json} personas={MOCK_RESULTS.personas_json} forcedTab={detailTab} />
        )}
      </div>
    </div>
  )
}

// ── Main component ────────────────────────────────────────────────────────────

export function LandingDemoWindow() {
  const [loopCount,    setLoopCount]    = useState(0)
  const [phase,        setPhase]        = useState<Phase>('home')
  const [typedChars,   setTypedChars]   = useState(0)
  const [runClicked,   setRunClicked]   = useState(false)
  const [sources,      setSources]      = useState<typeof MOCK_SOURCES>([])
  const [graphData,    setGraphData]    = useState<ContextGraphData | null>(null)
  const [personaCount, setPersonaCount] = useState(0)
  const [posts,        setPosts]        = useState<SocialPost[]>([])
  const [simRound,     setSimRound]     = useState(0)
  const [resultTab,    setResultTab]    = useState<ResultTab>('analysis')
  const [detailTab,    setDetailTab]    = useState<'feed' | 'personas'>('feed')
  const [activePlatform,  setActivePlatform]  = useState<Platform | undefined>(undefined)
  const [visible,         setVisible]         = useState(true)

  useEffect(() => {
    setPhase('home')
    setTypedChars(0)
    setRunClicked(false)
    setSources([])
    setGraphData(null)
    setPersonaCount(0)
    setPosts([])
    setSimRound(0)
    setResultTab('analysis')
    setDetailTab('feed')
    setActivePlatform(undefined)
    setVisible(true)

    const timers: ReturnType<typeof setTimeout>[] = []
    let t = 0
    const at = (delay: number, fn: () => void) => {
      t += delay
      timers.push(setTimeout(fn, t))
    }

    // ── Phase 1: Home ──────────────────────────────────────────────────────
    for (let i = 1; i <= 80; i++) {
      at(55, () => setTypedChars(c => c + 1))
    }
    at(150, () => setTypedChars(DEMO_INPUT.length))
    at(1000, () => setRunClicked(true))
    at(400, () => setVisible(false))
    at(300, () => { setPhase('simulate'); setVisible(true); setGraphData({ nodes: [], edges: [] }) })

    // ── Phase 2: Simulation ────────────────────────────────────────────────
    MOCK_SOURCES.forEach((src, i) => {
      at(i === 0 ? 350 : 320, () => {
        setSources(prev => [src, ...prev])
        if (i < MOCK_GRAPH_DATA.nodes.length) {
          const newNode = MOCK_GRAPH_DATA.nodes[i]
          setGraphData(prev => {
            if (!prev) return prev
            const existingIds = new Set(prev.nodes.map(n => n.id))
            const newEdges = MOCK_GRAPH_DATA.edges.filter(e =>
              (e.source === newNode.id && existingIds.has(e.target)) ||
              (e.target === newNode.id && existingIds.has(e.source))
            )
            return { nodes: [...prev.nodes, newNode], edges: [...prev.edges, ...newEdges] }
          })
        }
      })
    })
    at(500, () => setSources([]))
    MOCK_PERSONAS.forEach((_p, i) => {
      at(i === 0 ? 350 : 260, () => setPersonaCount(prev => prev + 1))
    })

    at(500, () => setSimRound(1))
    for (let i = 0; i < 6; i++) {
      const p = MOCK_POSTS[i]
      at(i === 0 ? 280 : 420, () => {
        setPosts(prev => [...prev, {
          id: `demo-1-${i}`, platform: p.platform,
          author_node_id: `n${i}`, author_name: p.author_name,
          content: p.content, action_type: p.action_type,
          round_num: 1, upvotes: 30 + i * 11,
          downvotes: i % 3 === 0 ? 1 : 0, parent_id: null,
        }])
      })
    }

    // 플랫폼 탭 순환 (round 1 포스트가 다 쌓인 뒤)
    at(600,  () => setActivePlatform('producthunt'))
    at(1100, () => setActivePlatform('indiehackers'))
    at(1100, () => setActivePlatform('reddit_startups'))
    at(1100, () => setActivePlatform('linkedin'))
    at(1100, () => setActivePlatform('hackernews'))

    at(500, () => setSimRound(2))
    for (let i = 6; i < 10; i++) {
      const p = MOCK_POSTS[i % MOCK_POSTS.length]
      at(i === 6 ? 280 : 380, () => {
        setPosts(prev => [...prev, {
          id: `demo-2-${i}`, platform: p.platform,
          author_node_id: `n${i}`, author_name: p.author_name,
          content: p.content, action_type: p.action_type,
          round_num: 2, upvotes: 20 + i * 8,
          downvotes: 0, parent_id: null,
        }])
      })
    }

    // ── Phase 3: Results ───────────────────────────────────────────────────
    at(700, () => setVisible(false))
    at(300, () => { setPhase('results'); setResultTab('analysis'); setVisible(true) })
    at(2500, () => setResultTab('simulation'))
    at(2500, () => setResultTab('final'))
    at(2500, () => { setResultTab('details'); setDetailTab('feed') })
    at(2500, () => setDetailTab('personas'))
    at(2500, () => setVisible(false))
    at(400, () => setLoopCount(c => c + 1))

    return () => timers.forEach(clearTimeout)
  }, [loopCount])

  const displayText = DEMO_INPUT.slice(0, typedChars)
  const personaPct  = Math.min(100, (personaCount / MOCK_PERSONAS.length) * 100)

  return (
    <div style={{
      border: `1px solid ${t.color.border}`,
      borderRadius: t.radius.lg,
      overflow: 'hidden',
      boxShadow: '0 4px 32px rgba(0,0,0,0.07)',
      background: t.color.bgPage,
      pointerEvents: 'none',
      userSelect: 'none',
    }}>
      {/* Browser chrome — traffic-light dots */}
      <div style={{
        background: t.color.bgCard,
        borderBottom: `1px solid ${t.color.border}`,
        padding: '9px 14px',
        display: 'flex', alignItems: 'center', gap: t.space[1],
      }}>
        <div style={{ width: 10, height: 10, borderRadius: '50%', background: '#fca5a5' }} />
        <div style={{ width: 10, height: 10, borderRadius: '50%', background: '#fcd34d' }} />
        <div style={{ width: 10, height: 10, borderRadius: '50%', background: '#86efac' }} />
        {phase === 'simulate' && simRound > 0 && (
          <span style={{
            marginLeft: 'auto',
            fontFamily: 'IBM Plex Mono, monospace',
            fontSize: t.font.size.xs, color: t.color.textMuted,
          }}>
            Round {simRound} · {posts.length} posts
          </span>
        )}
      </div>

      {/* Content area — fixed height, clipped */}
      <div style={{
        height: 580,
        overflow: 'hidden',
        opacity: visible ? 1 : 0,
        transition: 'opacity 0.3s ease',
      }}>
        {phase === 'home' && (
          <HomePhase displayText={displayText} runClicked={runClicked} />
        )}
        {phase === 'simulate' && (
          <SimulatePhase
            sources={sources}
            personaCount={personaCount}
            personaPct={personaPct}
            posts={posts}
            simRound={simRound}
            graphData={graphData}
            activePlatform={activePlatform}
          />
        )}
        {phase === 'results' && (
          <ResultsPhase tab={resultTab} detailTab={detailTab} />
        )}
      </div>
    </div>
  )
}
