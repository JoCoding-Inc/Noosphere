import { useEffect, useState } from 'react'
import { Header } from '../components/Header'
import { useMockSimulation } from '../hooks/useMockSimulation'
import { PlatformSimFeed } from '../components/PlatformSimFeed'
import { ReportView } from '../components/ReportView'
import { PersonaCardView } from '../components/PersonaCardView'
import { MarkdownView } from '../components/MarkdownView'
import type { Platform, SimResults } from '../types'

// ─── 데모 입력 텍스트 ───────────────────────────────────────────────────────
const DEMO_INPUT = `Noosphere is an AI-powered market simulator that predicts real-world reactions to your product before you launch.

Paste your landing page, pitch deck, or product description and Noosphere will:
- Collect context from GitHub, arXiv, Hacker News, Reddit, and more
- Generate 50+ AI personas representing your target audience
- Run multi-round social simulations across 5 tech platforms
- Deliver a structured analysis: verdict, sentiment by segment, key criticisms, and improvement suggestions

Built for founders, PMs, and product teams who want signal before noise.`

// ─── 목 결과 데이터 ─────────────────────────────────────────────────────────
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
}

// ─── 소스 색상 ───────────────────────────────────────────────────────────────
const SOURCE_COLORS: Record<string, string> = {
  github: '#24292e', arxiv: '#b91c1c', semantic_scholar: '#1d4ed8',
  hackernews: '#f97316', reddit: '#ef4444', product_hunt: '#da552f',
  itunes: '#fc3158', google_play: '#01875f', gdelt: '#7c3aed', serper: '#0891b2',
}

// ─── 데모 배너 ───────────────────────────────────────────────────────────────
function DemoBanner() {
  return (
    <div style={{
      background: 'linear-gradient(90deg, #8b5cf6, #6366f1)',
      color: '#fff', textAlign: 'center', fontSize: 12,
      padding: '6px 0', fontWeight: 500, letterSpacing: '0.02em',
    }}>
      ✦ DEMO MODE — no account required
    </div>
  )
}

// ─── 홈 화면 ─────────────────────────────────────────────────────────────────
const PLATFORM_OPTIONS = [
  { id: 'hackernews' as Platform, label: 'Hacker News', icon: '🟠' },
  { id: 'producthunt' as Platform, label: 'Product Hunt', icon: '🔴' },
  { id: 'indiehackers' as Platform, label: 'Indie Hackers', icon: '🟣' },
  { id: 'reddit_startups' as Platform, label: 'Reddit r/startups', icon: '🟤' },
  { id: 'linkedin' as Platform, label: 'LinkedIn', icon: '🔵' },
]

function DemoHomeView({ onRun }: { onRun: () => void }) {
  return (
    <main className="page-enter" style={{ maxWidth: 760, margin: '0 auto', padding: '52px 24px 80px' }}>
      <div style={{ marginBottom: 32 }}>
        <h1 style={{ fontSize: 34, fontWeight: 800, letterSpacing: '-0.04em', margin: '0 0 10px' }}>
          How will the market react?
        </h1>
        <p style={{ color: '#64748b', fontSize: 15, margin: 0 }}>
          Describe your product and simulate real-world reactions across tech communities.
        </p>
      </div>

      <textarea
        readOnly
        value={DEMO_INPUT}
        rows={9}
        style={{
          width: '100%', padding: '16px 18px', fontSize: 15,
          border: '1.5px solid #8b5cf6', borderRadius: 12,
          resize: 'none', fontFamily: 'inherit',
          boxSizing: 'border-box', background: '#fff',
          lineHeight: 1.6, outline: 'none',
          boxShadow: '0 0 0 3px rgba(139,92,246,0.12)',
          color: '#1e293b',
        }}
      />

      <div style={{ marginTop: 4, fontSize: 12, color: '#94a3b8' }}>
        Demo mode — using a pre-filled product description
      </div>

      <div style={{ marginTop: 16, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        {PLATFORM_OPTIONS.map(p => (
          <button key={p.id}
            style={{
              display: 'flex', alignItems: 'center', gap: 6,
              padding: '7px 14px', fontSize: 13, borderRadius: 8, cursor: 'default',
              border: '1.5px solid #1e293b',
              background: '#1e293b', color: '#fff',
              fontWeight: 600,
              boxShadow: '0 2px 8px rgba(30,41,59,0.25)',
            }}>
            <span>{p.icon}</span> {p.label}
          </button>
        ))}
      </div>

      <div style={{ marginTop: 20, display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
        <div style={{ fontSize: 13, color: '#94a3b8' }}>
          English · 12 rounds · 50 agents · ~470 sources
        </div>
      </div>

      <button
        onClick={onRun}
        className="run-btn"
        style={{
          marginTop: 24, padding: '14px 36px', fontSize: 15, fontWeight: 700,
          background: '#1e293b', color: '#fff',
          border: 'none', borderRadius: 10, cursor: 'pointer',
          letterSpacing: '-0.01em',
        }}>
        Run Demo Simulation →
      </button>
    </main>
  )
}

// ─── 시뮬레이션 화면 ──────────────────────────────────────────────────────────
function DemoSimulateView({ onDone }: { onDone: () => void }) {
  const sim = useMockSimulation()

  useEffect(() => {
    if (sim.status === 'done') {
      const t = setTimeout(onDone, 800)
      return () => clearTimeout(t)
    }
  }, [sim.status, onDone])

  const lastProgress = sim.events
    .filter(e => e.type === 'sim_progress')
    .map(e => (e as { type: 'sim_progress'; message: string }).message)
    .at(-1)

  const totalPosts = Object.values(sim.postsByPlatform).reduce((s, a) => s + (a?.length ?? 0), 0)

  const phase =
    sim.status === 'connecting' ? 'connecting' :
    sim.status === 'done' ? 'done' :
    sim.status === 'error' ? 'error' :
    sim.agentCount === 0 ? 'sourcing' :
    sim.roundNum === 0 && sim.personaCount < sim.agentCount ? 'personas' :
    sim.roundNum === 0 ? 'seeding' :
    'rounds'

  const phaseLabel: Record<string, string> = {
    connecting: 'Connecting...',
    sourcing: 'Searching sources...',
    personas: `Generating personas — ${sim.personaCount} / ${sim.agentCount}`,
    seeding: 'Initializing platforms...',
    rounds: `Round ${sim.roundNum} · ${totalPosts} posts`,
    done: 'Simulation complete — loading results...',
    error: 'Simulation failed',
  }

  const personaPct = sim.agentCount > 0
    ? Math.min(100, (sim.personaCount / sim.agentCount) * 100)
    : 0

  return (
    <main className="page-enter" style={{ maxWidth: 720, margin: '0 auto', padding: '48px 24px' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 8 }}>
        {sim.status !== 'error' && (
          <span style={{
            display: 'inline-block', width: 10, height: 10, borderRadius: '50%',
            background: phase === 'done' ? '#8b5cf6' : '#22c55e', flexShrink: 0,
            animation: phase === 'done' ? 'none' : 'pulse 1.5s infinite',
          }} />
        )}
        <h2
          className={phase !== 'error' && phase !== 'done' ? 'cursor-blink' : undefined}
          style={{ margin: 0, fontSize: 20, fontWeight: 700, letterSpacing: '-0.02em' }}
        >
          {phaseLabel[phase]}
        </h2>
      </div>

      {lastProgress && (
        <p key={lastProgress} style={{
          color: '#64748b', fontSize: 13, margin: '0 0 20px 22px',
          animation: 'fadeIn 0.3s ease',
        }}>
          {lastProgress}
        </p>
      )}

      {phase === 'personas' && sim.agentCount > 0 && (
        <div style={{ margin: '0 0 24px 0', animation: 'fadeInUp 0.3s ease' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, color: '#94a3b8', marginBottom: 6 }}>
            <span>Building agent personas</span>
            <span>{sim.personaCount} / {sim.agentCount}</span>
          </div>
          <div style={{ height: 6, background: '#e2e8f0', borderRadius: 3, overflow: 'hidden' }}>
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

      {sim.sourceTimeline.length > 0 && phase === 'sourcing' && (
        <div style={{ marginBottom: 20 }}>
          <div style={{ fontSize: 11, color: '#94a3b8', marginBottom: 8 }}>
            {sim.sourceTimeline.length} items collected
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {sim.sourceTimeline.map((item, i) => (
              <div key={`${item.source}-${i}`} className="source-item" style={{
                padding: '8px 12px', borderRadius: 8,
                background: '#fff', border: '1px solid #e2e8f0',
                borderLeft: `3px solid ${SOURCE_COLORS[item.source] || '#94a3b8'}`,
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 3 }}>
                  <span style={{
                    fontSize: 10, fontWeight: 700, padding: '1px 6px', borderRadius: 8,
                    background: SOURCE_COLORS[item.source] ? `${SOURCE_COLORS[item.source]}18` : '#f1f5f9',
                    color: SOURCE_COLORS[item.source] || '#64748b',
                    textTransform: 'uppercase', letterSpacing: '0.04em',
                  }}>
                    {item.source}
                  </span>
                </div>
                <div style={{ fontSize: 13, fontWeight: 600, color: '#1e293b', lineHeight: 1.4 }}>
                  {item.title}
                </div>
                {item.snippet && (
                  <div style={{ fontSize: 12, color: '#64748b', marginTop: 3, lineHeight: 1.5 }}>
                    {item.snippet}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {totalPosts > 0 && (
        <div style={{ borderTop: '1px solid #e2e8f0', paddingTop: 20 }}>
          <PlatformSimFeed postsByPlatform={sim.postsByPlatform} ideaText="Noosphere – AI market simulator" />
        </div>
      )}

      {totalPosts === 0 && sim.sourceTimeline.length === 0 && phase !== 'error' && phase !== 'done' && (
        <div style={{
          marginTop: 48, textAlign: 'center', color: '#94a3b8', fontSize: 14,
          animation: 'fadeIn 0.5s ease',
        }}>
          <div style={{ fontSize: 28, marginBottom: 12 }}>⚙️</div>
          Waiting for simulation to start...
        </div>
      )}
    </main>
  )
}

// ─── 결과 화면 ────────────────────────────────────────────────────────────────
type Tab = 'analysis' | 'report' | 'feed' | 'personas'

function DemoResultView({ onReset }: { onReset: () => void }) {
  const [tab, setTab] = useState<Tab>('analysis')

  const tabs: { id: Tab; label: string }[] = [
    { id: 'analysis', label: 'Analysis' },
    { id: 'report', label: 'Simulation' },
    { id: 'feed', label: 'Social Feed' },
    { id: 'personas', label: 'Personas' },
  ]

  return (
    <main className="page-enter" style={{ maxWidth: 900, margin: '0 auto', padding: '32px 24px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <button onClick={onReset}
          style={{ background: 'none', border: 'none', color: '#64748b', cursor: 'pointer', fontSize: 14 }}>
          ← Run demo again
        </button>
        <div style={{
          fontSize: 12, padding: '4px 12px', borderRadius: 20,
          background: 'rgba(139,92,246,0.1)', color: '#8b5cf6', fontWeight: 600,
        }}>
          Demo Results
        </div>
      </div>

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24, borderBottom: '1px solid #e2e8f0' }}>
        <div style={{ display: 'flex', gap: 4 }}>
          {tabs.map(t => (
            <button key={t.id} onClick={() => setTab(t.id)}
              style={{
                padding: '10px 20px', fontSize: 14, cursor: 'pointer', border: 'none',
                background: 'none', fontWeight: tab === t.id ? 600 : 400,
                borderBottom: tab === t.id ? '2px solid #1e293b' : '2px solid transparent',
                color: tab === t.id ? '#1e293b' : '#64748b',
                transition: 'color 0.15s, border-color 0.15s',
              }}>
              {t.label}
            </button>
          ))}
        </div>
        <a
          href="/noosphere-demo-report.pdf"
          download
          style={{
            display: 'inline-block', padding: '8px 18px', background: '#1e293b',
            color: '#fff', borderRadius: 8, textDecoration: 'none', fontSize: 13,
            fontWeight: 600, marginBottom: 4,
          }}>
          ↓ Download PDF
        </a>
      </div>

      <div key={tab} className="tab-content">
        {tab === 'analysis' && (
          <MarkdownView content={MOCK_RESULTS.analysis_md} />
        )}
        {tab === 'report' && (
          <ReportView report={MOCK_RESULTS.report_json} simId="demo" />
        )}
        {tab === 'feed' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            {Object.entries(MOCK_RESULTS.posts_json).flatMap(([, posts]) => posts ?? []).map(post => (
              <div key={post.id} style={{
                background: '#fff', border: '1px solid #e2e8f0', borderRadius: 10,
                padding: '16px 18px',
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                  <span style={{
                    fontSize: 11, fontWeight: 700, padding: '2px 8px', borderRadius: 10,
                    background: '#f1f5f9', color: '#475569',
                    textTransform: 'capitalize',
                  }}>
                    {post.platform.replace('_', ' ')}
                  </span>
                  <span style={{ fontSize: 13, fontWeight: 600, color: '#1e293b' }}>{post.author_name}</span>
                  <span style={{ fontSize: 12, color: '#94a3b8', marginLeft: 'auto' }}>Round {post.round_num}</span>
                </div>
                <p style={{ margin: 0, fontSize: 14, color: '#374151', lineHeight: 1.6 }}>{post.content}</p>
                <div style={{ marginTop: 8, display: 'flex', gap: 12, fontSize: 12, color: '#94a3b8' }}>
                  <span>▲ {post.upvotes}</span>
                  {post.downvotes > 0 && <span>▼ {post.downvotes}</span>}
                </div>
              </div>
            ))}
          </div>
        )}
        {tab === 'personas' && (
          <PersonaCardView personas={MOCK_RESULTS.personas_json} />
        )}
      </div>
    </main>
  )
}

// ─── 메인 DemoPage ────────────────────────────────────────────────────────────
type DemoPhase = 'home' | 'simulate' | 'result'

export function DemoPage() {
  const [phase, setPhase] = useState<DemoPhase>('home')

  return (
    <div style={{ minHeight: '100vh', background: '#f8fafc' }}>
      <Header />
      <DemoBanner />

      {phase === 'home' && (
        <DemoHomeView onRun={() => setPhase('simulate')} />
      )}
      {phase === 'simulate' && (
        <DemoSimulateView onDone={() => setPhase('result')} />
      )}
      {phase === 'result' && (
        <DemoResultView onReset={() => setPhase('home')} />
      )}
    </div>
  )
}
