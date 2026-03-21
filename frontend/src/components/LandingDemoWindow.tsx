import { useEffect, useState } from 'react'
import { MOCK_SOURCES, MOCK_PERSONAS, MOCK_POSTS } from '../hooks/useMockSimulation'
import { SOURCE_COLORS } from '../constants'
import type { Platform, SocialPost } from '../types'

// ── Mock results (extracted from DemoPage) ───────────────────────────────────

const MOCK_REPORT = {
  verdict: 'mixed' as const,
  segments: [
    { name: 'Hacker News',       sentiment: 'neutral'  as const, summary: 'Technical community engaged but skeptical. Strong interest in methodology and simulation fidelity.' },
    { name: 'Product Hunt',      sentiment: 'positive' as const, summary: 'Practitioners immediately connected with the pain point. Strong upvote potential.' },
    { name: 'Indie Hackers',     sentiment: 'positive' as const, summary: 'Highly favorable reception. IH users acutely aware of positioning risk.' },
    { name: 'Reddit r/startups', sentiment: 'neutral'  as const, summary: 'Mixed reception with constructive skepticism.' },
    { name: 'LinkedIn',          sentiment: 'positive' as const, summary: 'Professional audience responded well to structured output and GTM framing.' },
  ],
}

const DEMO_INPUT = `Noosphere is an AI-powered market simulator that predicts real-world reactions to your product before you launch.

Paste your landing page, pitch deck, or product description and Noosphere will:
- Collect context from GitHub, arXiv, Hacker News, Reddit, and more
- Generate 50+ AI personas representing your target audience
- Run multi-round social simulations across 5 tech platforms
- Deliver a structured analysis: verdict, sentiment by segment, key criticisms`

const PLATFORM_LABELS: Record<Platform, string> = {
  hackernews:      'Hacker News',
  producthunt:     'Product Hunt',
  indiehackers:    'Indie Hackers',
  reddit_startups: 'Reddit r/startups',
  linkedin:        'LinkedIn',
}

const SENTIMENT_COLOR: Record<string, string> = {
  positive: '#22c55e',
  neutral:  '#f59e0b',
  negative: '#ef4444',
}

type Phase = 'home' | 'simulate' | 'results'
type ResultTab = 'report' | 'feed' | 'analysis'

// ── Sub-components (display-only, no event handlers) ─────────────────────────

function HomePhase({ displayText, runClicked }: { displayText: string; runClicked: boolean }) {
  return (
    <div style={{ padding: '28px 28px 24px' }}>
      <h2 style={{ fontSize: 20, fontWeight: 800, letterSpacing: '-0.03em', margin: '0 0 7px', color: '#0f172a' }}>
        How will the market react?
      </h2>
      <p style={{ color: '#64748b', fontSize: 12, margin: '0 0 14px' }}>
        Describe your product and simulate real-world reactions across tech communities.
      </p>
      <div style={{
        width: '100%', padding: '11px 13px',
        fontSize: 11.5, border: '1.5px solid #8b5cf6',
        borderRadius: 9, background: '#fff',
        fontFamily: 'inherit', lineHeight: 1.6,
        color: '#1e293b',
        boxShadow: '0 0 0 3px rgba(139,92,246,0.1)',
        minHeight: 110, whiteSpace: 'pre-wrap',
        wordBreak: 'break-word',
      }}>
        {displayText}
        {displayText.length < DEMO_INPUT.length && (
          <span className="cursor-blink" style={{ display: 'inline' }} />
        )}
      </div>
      <div style={{ marginTop: 11, display: 'flex', gap: 5, flexWrap: 'wrap' }}>
        {(Object.keys(PLATFORM_LABELS) as Platform[]).map(p => (
          <span key={p} style={{
            display: 'inline-flex', alignItems: 'center', gap: 5,
            padding: '4px 10px', fontSize: 11, borderRadius: 7,
            border: '1.5px solid #1e293b',
            background: '#1e293b', color: '#fff', fontWeight: 600,
          }}>
            {PLATFORM_LABELS[p]}
          </span>
        ))}
      </div>
      <div style={{
        marginTop: 14, padding: '10px 22px', fontSize: 12, fontWeight: 700,
        background: '#1e293b', color: '#fff',
        border: 'none', borderRadius: 8, display: 'inline-block',
        letterSpacing: '-0.01em',
        animation: runClicked ? 'runClick 200ms ease forwards' : 'none',
      }}>
        Run Simulation →
      </div>
    </div>
  )
}

function SimulatePhase({
  sources, personaCount, personaPct, posts, simRound,
}: {
  sources: typeof MOCK_SOURCES
  personaCount: number
  personaPct: number
  posts: SocialPost[]
  simRound: number
}) {
  const showSources  = sources.length > 0
  const showPersonas = sources.length === 0 && personaCount > 0 && simRound === 0
  const showPosts    = simRound > 0

  const phaseLabel = showSources
    ? 'Searching sources...'
    : showPersonas
    ? `Generating personas — ${personaCount} / ${MOCK_PERSONAS.length}`
    : showPosts
    ? `Round ${simRound} · ${posts.length} posts`
    : 'Initializing...'

  return (
    <div style={{ padding: '20px 24px', height: '100%', overflowY: 'hidden' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 9, marginBottom: 12 }}>
        <span style={{
          width: 8, height: 8, borderRadius: '50%',
          background: '#22c55e', flexShrink: 0, display: 'inline-block',
          animation: 'pulse 1.5s infinite',
        }} />
        <span
          className={showPosts ? '' : 'cursor-blink'}
          style={{ fontSize: 14, fontWeight: 700, color: '#1e293b', letterSpacing: '-0.02em' }}
        >
          {phaseLabel}
        </span>
      </div>

      {showPersonas && (
        <div style={{ marginBottom: 14 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: '#94a3b8', marginBottom: 5 }}>
            <span>Building agent personas</span>
            <span>{personaCount} / {MOCK_PERSONAS.length}</span>
          </div>
          <div style={{ height: 5, background: '#e2e8f0', borderRadius: 3, overflow: 'hidden' }}>
            <div style={{
              height: '100%', borderRadius: 3,
              background: 'linear-gradient(90deg, #6355e0, #8070ff)',
              width: `${personaPct}%`,
              transition: 'width 0.3s ease',
              boxShadow: '0 0 6px rgba(99,85,224,0.4)',
            }} />
          </div>
        </div>
      )}

      {showSources && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
          {sources.slice(0, 5).map((src, i) => (
            <div key={i} className="source-item" style={{
              padding: '7px 10px', borderRadius: 7,
              background: '#f8fafc', border: '1px solid #e2e8f0',
              borderLeft: `3px solid ${SOURCE_COLORS[src.source as keyof typeof SOURCE_COLORS] || '#94a3b8'}`,
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 2 }}>
                <span style={{
                  fontSize: 9, fontWeight: 700, padding: '1px 5px', borderRadius: 4,
                  background: `${SOURCE_COLORS[src.source as keyof typeof SOURCE_COLORS] || '#94a3b8'}18`,
                  color: SOURCE_COLORS[src.source as keyof typeof SOURCE_COLORS] || '#64748b',
                  textTransform: 'uppercase', letterSpacing: '0.04em',
                  fontFamily: 'IBM Plex Mono, monospace',
                }}>
                  {src.source}
                </span>
              </div>
              <div style={{ fontSize: 11, fontWeight: 600, color: '#1e293b', lineHeight: 1.4 }}>
                {src.title}
              </div>
            </div>
          ))}
        </div>
      )}

      {showPosts && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          {posts.slice(-4).map(post => (
            <div key={post.id} className="post-item" style={{
              padding: '9px 12px', borderRadius: 8,
              border: '1px solid #e2e8f0', background: '#fff',
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
                <span style={{
                  fontSize: 9, fontWeight: 700, padding: '1px 6px', borderRadius: 5,
                  background: '#f1f5f9', color: '#475569',
                  textTransform: 'uppercase', fontFamily: 'IBM Plex Mono, monospace',
                }}>
                  {post.platform.replace('_', ' ')}
                </span>
                <span style={{ fontSize: 11, fontWeight: 600, color: '#1e293b' }}>{post.author_name}</span>
              </div>
              <p style={{ margin: 0, fontSize: 11, color: '#374151', lineHeight: 1.5 }}>
                {post.content.slice(0, 100)}{post.content.length > 100 ? '...' : ''}
              </p>
              <div style={{ marginTop: 4, fontSize: 10, color: '#94a3b8' }}>▲ {post.upvotes}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function ResultsPhase({ tab }: { tab: ResultTab }) {
  const tabs: { id: ResultTab; label: string }[] = [
    { id: 'report',   label: 'Simulation' },
    { id: 'feed',     label: 'Social Feed' },
    { id: 'analysis', label: 'Analysis' },
  ]

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <div style={{ display: 'flex', borderBottom: '1px solid #e2e8f0', padding: '0 16px', flexShrink: 0 }}>
        {tabs.map(t => (
          <div key={t.id} style={{
            padding: '10px 14px', fontSize: 12, cursor: 'default',
            fontWeight: tab === t.id ? 600 : 400,
            borderBottom: tab === t.id ? '2px solid #1e293b' : '2px solid transparent',
            color: tab === t.id ? '#1e293b' : '#64748b',
            transition: 'color 0.15s, border-color 0.15s',
          }}>
            {t.label}
          </div>
        ))}
      </div>

      <div key={tab} className="tab-content" style={{ flex: 1, overflow: 'hidden', padding: '14px 18px' }}>
        {tab === 'report' && (
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 14 }}>
              <span style={{
                fontSize: 11, fontWeight: 700, padding: '3px 10px', borderRadius: 20,
                background: '#fef3c7', color: '#d97706', border: '1px solid #fde68a',
                fontFamily: 'IBM Plex Mono, monospace', textTransform: 'uppercase',
              }}>
                Mixed
              </span>
              <span style={{ fontSize: 11, color: '#64748b' }}>127 signals · 5 platforms</span>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
              {MOCK_REPORT.segments.map(seg => (
                <div key={seg.name} style={{
                  display: 'flex', alignItems: 'center', gap: 9,
                  padding: '7px 11px', borderRadius: 7,
                  border: '1px solid #e2e8f0', background: '#f8fafc',
                }}>
                  <span style={{
                    width: 7, height: 7, borderRadius: '50%', flexShrink: 0,
                    background: SENTIMENT_COLOR[seg.sentiment],
                  }} />
                  <span style={{ fontSize: 11, fontWeight: 600, color: '#1e293b', width: 120, flexShrink: 0 }}>
                    {seg.name}
                  </span>
                  <span style={{ fontSize: 10.5, color: '#64748b', lineHeight: 1.4 }}>
                    {seg.summary.slice(0, 55)}...
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {tab === 'feed' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 7 }}>
            {[
              { platform: 'producthunt', author: 'priya_builds', content: '🚀 This is exactly what I needed before my last launch. Would have saved me weeks of misaligned positioning. Upvoted!', upvotes: 54 },
              { platform: 'hackernews',  author: 'rachel_cto',   content: 'The technical implementation here is more interesting than the product surface suggests. LLM-based agent simulation with network effects modeled in?', upvotes: 89 },
              { platform: 'linkedin',    author: 'Sarah K.',      content: 'As a PM, the ability to stress-test messaging across different communities before launch is massive. The persona diversity feels real.', upvotes: 76 },
            ].map((post, i) => (
              <div key={i} style={{
                padding: '9px 11px', borderRadius: 8,
                border: '1px solid #e2e8f0', background: '#fff',
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
                  <span style={{
                    fontSize: 9, fontWeight: 700, padding: '1px 6px', borderRadius: 5,
                    background: '#f1f5f9', color: '#475569', textTransform: 'capitalize',
                    fontFamily: 'IBM Plex Mono, monospace',
                  }}>
                    {post.platform.replace('_', ' ')}
                  </span>
                  <span style={{ fontSize: 11, fontWeight: 600, color: '#1e293b' }}>{post.author}</span>
                  <span style={{ fontSize: 10, color: '#94a3b8', marginLeft: 'auto' }}>▲ {post.upvotes}</span>
                </div>
                <p style={{ margin: 0, fontSize: 11, color: '#374151', lineHeight: 1.5 }}>{post.content}</p>
              </div>
            ))}
          </div>
        )}

        {tab === 'analysis' && (
          <div>
            <div style={{ fontSize: 15, fontWeight: 700, color: '#0f172a', marginBottom: 6 }}>
              Market Analysis — Noosphere
            </div>
            <div style={{ fontSize: 11, color: '#64748b', marginBottom: 10 }}>
              <strong style={{ color: '#475569' }}>Domain:</strong> AI / Developer Tools · SaaS
            </div>
            <div style={{ fontSize: 12, fontWeight: 700, color: '#1e293b', marginBottom: 5 }}>Executive Summary</div>
            <p style={{ fontSize: 11, color: '#374151', lineHeight: 1.65, margin: 0 }}>
              Noosphere enters a nascent but rapidly growing category of AI-driven market intelligence tools.
              The concept of simulating social reactions before launch resonates strongly with founders and
              product managers who have experienced costly positioning mistakes post-launch.
            </p>
            <p style={{ fontSize: 11, color: '#374151', lineHeight: 1.65, margin: '8px 0 0' }}>
              Across all five simulated platforms, the overall reception was <strong>cautiously optimistic</strong>.
              Technical communities exhibited healthy skepticism, while practitioner communities responded with enthusiasm.
            </p>
          </div>
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
  const [personaCount, setPersonaCount] = useState(0)
  const [posts,        setPosts]        = useState<SocialPost[]>([])
  const [simRound,     setSimRound]     = useState(0)
  const [resultTab,    setResultTab]    = useState<ResultTab>('report')
  const [visible,      setVisible]      = useState(true)

  useEffect(() => {
    // Reset for this loop iteration
    setPhase('home')
    setTypedChars(0)
    setRunClicked(false)
    setSources([])
    setPersonaCount(0)
    setPosts([])
    setSimRound(0)
    setResultTab('report')
    setVisible(true)

    const timers: ReturnType<typeof setTimeout>[] = []
    let t = 0
    const at = (delay: number, fn: () => void) => {
      t += delay
      timers.push(setTimeout(fn, t))
    }

    // ── Phase 1: Home ──────────────────────────────────────────────────────
    // Type first 80 chars one by one, then jump to full
    for (let i = 1; i <= 80; i++) {
      at(55, () => setTypedChars(c => c + 1))
    }
    at(150, () => setTypedChars(DEMO_INPUT.length))

    // Run button click animation
    at(1000, () => setRunClicked(true))

    // Fade out → transition to simulate
    at(400, () => setVisible(false))
    at(300, () => {
      setPhase('simulate')
      setVisible(true)
    })

    // ── Phase 2: Simulation ────────────────────────────────────────────────
    // Sources appear one by one (prepend — newest on top)
    MOCK_SOURCES.forEach((src, i) => {
      at(i === 0 ? 350 : 320, () => {
        setSources(prev => [src, ...prev])
      })
    })

    // Clear sources, start persona generation
    at(500, () => setSources([]))
    MOCK_PERSONAS.forEach((_p, i) => {
      at(i === 0 ? 350 : 260, () => {
        setPersonaCount(prev => prev + 1)
      })
    })

    // Round 1 posts
    at(500, () => setSimRound(1))
    for (let i = 0; i < 6; i++) {
      const p = MOCK_POSTS[i]
      at(i === 0 ? 280 : 420, () => {
        setPosts(prev => [...prev, {
          id: `demo-1-${i}`,
          platform: p.platform,
          author_node_id: `n${i}`,
          author_name: p.author_name,
          content: p.content,
          action_type: p.action_type,
          round_num: 1,
          upvotes: 30 + i * 11,
          downvotes: i % 3 === 0 ? 1 : 0,
          parent_id: null,
        }])
      })
    }

    // Round 2 posts
    at(500, () => setSimRound(2))
    for (let i = 6; i < 10; i++) {
      const p = MOCK_POSTS[i % MOCK_POSTS.length]
      at(i === 6 ? 280 : 380, () => {
        setPosts(prev => [...prev, {
          id: `demo-2-${i}`,
          platform: p.platform,
          author_node_id: `n${i}`,
          author_name: p.author_name,
          content: p.content,
          action_type: p.action_type,
          round_num: 2,
          upvotes: 20 + i * 8,
          downvotes: 0,
          parent_id: null,
        }])
      })
    }

    // Fade out → results
    at(700, () => setVisible(false))
    at(300, () => {
      setPhase('results')
      setResultTab('report')
      setVisible(true)
    })

    // ── Phase 3: Results ───────────────────────────────────────────────────
    at(3200, () => setResultTab('feed'))
    at(3000, () => setResultTab('analysis'))
    at(2800, () => setVisible(false))

    // Restart loop
    at(400, () => setLoopCount(c => c + 1))

    return () => timers.forEach(clearTimeout)
  }, [loopCount])

  const displayText  = DEMO_INPUT.slice(0, typedChars)
  const personaPct   = Math.min(100, (personaCount / MOCK_PERSONAS.length) * 100)

  return (
    <div style={{
      border: '1px solid #e2e8f0',
      borderRadius: 12,
      overflow: 'hidden',
      boxShadow: '0 4px 32px rgba(0,0,0,0.07)',
      background: '#fff',
      pointerEvents: 'none',
      userSelect: 'none',
    }}>
      {/* Top bar — traffic-light dots only, no label */}
      <div style={{
        background: '#f8fafc',
        borderBottom: '1px solid #e2e8f0',
        padding: '9px 14px',
        display: 'flex', alignItems: 'center', gap: 6,
      }}>
        <div style={{ width: 10, height: 10, borderRadius: '50%', background: '#fca5a5' }} />
        <div style={{ width: 10, height: 10, borderRadius: '50%', background: '#fcd34d' }} />
        <div style={{ width: 10, height: 10, borderRadius: '50%', background: '#86efac' }} />
        {phase === 'simulate' && simRound > 0 && (
          <span style={{
            marginLeft: 'auto',
            fontFamily: 'IBM Plex Mono, monospace',
            fontSize: 10, color: '#94a3b8',
          }}>
            Round {simRound} · {posts.length} posts
          </span>
        )}
      </div>

      {/* Content area — fixed height, clipped */}
      <div style={{
        height: 420,
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
          />
        )}
        {phase === 'results' && (
          <ResultsPhase tab={resultTab} />
        )}
      </div>
    </div>
  )
}
