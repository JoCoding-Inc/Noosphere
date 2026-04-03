import { useEffect, useMemo, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { t } from '../tokens'
import { Header } from '../components/Header'
import { ReportView } from '../components/ReportView'
import { DetailsView } from '../components/DetailsView'
import { MarkdownView } from '../components/MarkdownView'
import { SourcesView } from '../components/SourcesView'
import { SimulationAnalytics } from '../components/SimulationAnalytics'
import type { RoundStat } from '../components/SimulationAnalytics'
import { TopPosts } from '../components/TopPosts'
import { getResults, exportPdfUrl } from '../api'
import type { SimResults, SocialPost, Platform, Persona } from '../types'

type Tab = 'analysis' | 'simulation' | 'launch' | 'final' | 'details'

function computeRoundStats(posts: Partial<Record<Platform, SocialPost[]>>): RoundStat[] {
  const allPosts = Object.values(posts).flatMap(list => list ?? [])
  const roundMap = new Map<number, { authors: Set<string>; newPosts: number; newComments: number }>()

  for (const p of allPosts) {
    if (p.round_num == null) continue
    let bucket = roundMap.get(p.round_num)
    if (!bucket) {
      bucket = { authors: new Set(), newPosts: 0, newComments: 0 }
      roundMap.set(p.round_num, bucket)
    }
    bucket.authors.add(p.author_node_id)
    if (p.parent_id) {
      bucket.newComments++
    } else {
      bucket.newPosts++
    }
  }

  return Array.from(roundMap.entries())
    .sort((a, b) => a[0] - b[0])
    .map(([round, data]) => ({
      round,
      totalActiveAgents: data.authors.size,
      totalNewPosts: data.newPosts,
      totalNewComments: data.newComments,
    }))
}

const PLATFORM_SHORT: Record<string, string> = {
  hackernews: 'HN', producthunt: 'PH', indiehackers: 'IH',
  reddit_startups: 'Reddit', linkedin: 'LinkedIn',
}

function PlatformComparison({
  posts,
  personas,
}: {
  posts: Partial<Record<Platform, SocialPost[]>>
  personas: Partial<Record<Platform, Persona[]>>
}) {
  const platforms = Object.keys(posts) as Platform[]
  if (platforms.length === 0) return null

  return (
    <div style={{ marginBottom: 24 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#6366f1" strokeWidth="2" aria-hidden="true">
          <rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/>
          <rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/>
        </svg>
        <span style={{ fontSize: t.font.size.lg, fontWeight: t.font.weight.bold, color: t.color.primary }}>Platform Comparison</span>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: `repeat(${Math.min(platforms.length, 5)}, 1fr)`, gap: 10 }}>
        {platforms.map(platform => {
          const platformPosts = posts[platform] ?? []
          const total = platformPosts.length
          const pos = platformPosts.filter(p => p.sentiment === 'positive').length
          const neu = platformPosts.filter(p => p.sentiment === 'neutral').length
          const neg = platformPosts.filter(p => p.sentiment === 'negative').length
          const con = platformPosts.filter(p => p.sentiment === 'constructive').length
          const posPct = total > 0 ? Math.round((pos / total) * 100) : 0
          const neuPct = total > 0 ? Math.round((neu / total) * 100) : 0
          const negPct = total > 0 ? Math.round((neg / total) * 100) : 0
          const conPct = total > 0 ? Math.round((con / total) * 100) : 0

          // Find most active agent
          const authorCounts = new Map<string, number>()
          for (const p of platformPosts) {
            authorCounts.set(p.author_node_id, (authorCounts.get(p.author_node_id) ?? 0) + 1)
          }
          let topAuthorId = ''
          let topCount = 0
          for (const [id, count] of authorCounts) {
            if (count > topCount) { topAuthorId = id; topCount = count }
          }
          // Lookup name from personas
          const platformPersonas = personas[platform] ?? []
          const topPersona = platformPersonas.find(p => p.node_id === topAuthorId)
          // Fallback: check post author_name
          const topName = topPersona?.name ?? platformPosts.find(p => p.author_node_id === topAuthorId)?.author_name ?? ''

          return (
            <div key={platform} style={{
              background: t.color.bgPage, border: `1px solid ${t.color.border}`, borderRadius: t.radius.md,
              padding: t.space[3], boxShadow: '0 1px 3px rgba(0,0,0,0.04)',
            }}>
              <div style={{ fontSize: t.font.size.sm, fontWeight: t.font.weight.bold, color: t.color.textPrimary, marginBottom: 6 }}>
                {PLATFORM_SHORT[platform] ?? platform}
              </div>
              <div style={{ fontSize: t.font.size['2xl'], fontWeight: t.font.weight.bold, color: t.color.primary, marginBottom: 6 }}>
                {total}
                <span style={{ fontSize: t.font.size.xs, fontWeight: t.font.weight.normal, color: t.color.textMuted, marginLeft: 4 }}>posts</span>
              </div>
              {/* Sentiment mini-bar */}
              <div style={{ display: 'flex', height: 5, borderRadius: 3, overflow: 'hidden', background: t.color.border, marginBottom: 6 }}>
                {posPct > 0 && <div style={{ width: `${posPct}%`, background: t.color.success }} />}
                {neuPct > 0 && <div style={{ width: `${neuPct}%`, background: t.color.textMuted }} />}
                {negPct > 0 && <div style={{ width: `${negPct}%`, background: t.color.danger }} />}
                {conPct > 0 && <div style={{ width: `${conPct}%`, background: t.color.info }} />}
              </div>
              <div style={{ display: 'flex', gap: 6, fontSize: 9, color: t.color.textMuted, marginBottom: 6 }}>
                <span>{posPct}% pos</span>
                <span>{neuPct}% neu</span>
                <span>{negPct}% neg</span>
                {conPct > 0 && <span>{conPct}% con</span>}
              </div>
              {topName && (
                <div style={{ fontSize: 10, color: t.color.textSecondary, borderTop: `1px solid ${t.color.bgSubtle}`, paddingTop: 4 }}>
                  Most active: <span style={{ fontWeight: t.font.weight.semibold, color: t.color.textPrimary }}>{topName}</span>
                  <span style={{ color: t.color.textMuted }}> ({topCount})</span>
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}

export function ResultPage() {
  const { simId } = useParams<{ simId: string }>()
  const navigate = useNavigate()
  const [results, setResults] = useState<SimResults | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [tab, setTab] = useState<Tab>('analysis')
  const [sourcesOpen, setSourcesOpen] = useState(false)
  const [selectedRound, setSelectedRound] = useState<number>(0)
  const [copied, setCopied] = useState(false)

  const copyableContent: Partial<Record<Tab, string | null | undefined>> = results ? {
    analysis: results.analysis_md,
    launch:   results.gtm_md,
    final:    results.final_report_md,
  } : {}

  function handleCopy() {
    const content = copyableContent[tab]
    if (!content) return
    navigator.clipboard.writeText(content).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }

  useEffect(() => {
    if (!simId) return
    getResults(simId)
      .then(setResults)
      .catch(e => setError(e instanceof Error ? e.message : 'Unknown error'))
      .finally(() => setLoading(false))
  }, [simId])

  const tabs: { id: Tab; label: string }[] = [
    { id: 'analysis',   label: 'Analysis' },
    { id: 'simulation', label: 'Simulation' },
    { id: 'launch',     label: 'Launch Strategy' },
    { id: 'final',      label: 'Final Report' },
    { id: 'details',    label: 'Details' },
  ]

  const roundStats = useMemo(
    () => results ? computeRoundStats(results.posts_json) : [],
    [results]
  )

  const personasMap = useMemo(() => {
    if (!results) return {}
    const map: Record<string, Persona> = {}
    for (const personas of Object.values(results.personas_json)) {
      for (const p of personas ?? []) {
        map[p.node_id] = p
      }
    }
    return map
  }, [results])

  // sentiment_timeline의 모든 라운드 segment_distribution을 merge (합산)
  const mergedSegmentDist = useMemo(() => {
    const report = results?.report_json
    const dist: Record<string, number> = {};
    (report?.sentiment_timeline ?? []).forEach(entry => {
      const sd = (entry as any).segment_distribution
      if (sd && typeof sd === 'object') {
        Object.entries(sd).forEach(([seg, cnt]) => {
          dist[seg] = (dist[seg] ?? 0) + (cnt as number)
        })
      }
    })
    return Object.keys(dist).length > 0 ? dist : undefined
  }, [results])

  const maxRound = useMemo(() => {
    if (!results) return 0
    const allPosts = Object.values(results.posts_json).flatMap(list => list ?? [])
    return allPosts.reduce((max, p) => Math.max(max, p.round_num ?? 0), 0)
  }, [results])

  const filteredPostsByPlatform = useMemo(() => {
    if (!results) return {}
    if (selectedRound === 0) return results.posts_json
    const filtered: Partial<Record<Platform, SocialPost[]>> = {}
    for (const [platform, posts] of Object.entries(results.posts_json)) {
      filtered[platform as Platform] = (posts ?? []).filter(p => p.round_num === selectedRound)
    }
    return filtered
  }, [results, selectedRound])


  return (
    <div style={{ minHeight: '100vh', background: t.color.bgBody }}>
      <Header />
      <main className="page-enter" style={{ maxWidth: 1280, margin: '0 auto', padding: `${t.space[8]} ${t.space[6]}` }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: t.space[6] }}>
          <button onClick={() => navigate('/app')}
            style={{ background: 'none', border: 'none', color: t.color.textSecondary, cursor: 'pointer', fontSize: t.font.size.lg }}>
            ← New simulation
          </button>
        </div>

        {loading && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, color: t.color.textSecondary, fontSize: t.font.size.lg }}>
            <span className="spinner" style={{ borderColor: 'rgba(100,116,139,0.3)', borderTopColor: t.color.textSecondary }} />
            Loading results...
          </div>
        )}
        {error && <p role="alert" style={{ color: t.color.danger }}>{error}</p>}

        {results && (
          <>
            {/* PDF download — always visible above tabs */}
            <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 12 }}>
              <a
                href={exportPdfUrl(simId ?? '')}
                download
                style={{
                  display: 'inline-block', padding: `${t.space[2]} 18px`, background: t.color.primary,
                  color: t.color.textInverse, borderRadius: t.radius.md, textDecoration: 'none', fontSize: t.font.size.md,
                  fontWeight: t.font.weight.semibold,
                }}>
                ↓ Download Report PDF
              </a>
            </div>
            {/* Tab navigation */}
            <div className="result-tabs" style={{ display: 'flex', gap: 4, marginBottom: t.space[6], borderBottom: `1px solid ${t.color.border}` }}>
              {tabs.map(tab_ => (
                <button key={tab_.id} onClick={() => setTab(tab_.id)}
                  style={{
                    padding: '10px 20px', fontSize: t.font.size.lg, cursor: 'pointer', border: 'none',
                    background: 'none', fontWeight: tab === tab_.id ? t.font.weight.semibold : t.font.weight.normal,
                    borderBottom: tab === tab_.id ? `2px solid ${t.color.primary}` : '2px solid transparent',
                    color: tab === tab_.id ? t.color.primary : t.color.textSecondary,
                    transition: 'color 0.15s, border-color 0.15s',
                  }}>
                  {tab_.label}
                </button>
              ))}
            </div>

            <div key={tab} className="tab-content">
              {tab === 'analysis' && (
                <div style={{ position: 'relative' }}>
                  <button onClick={handleCopy} style={{
                    position: 'absolute', top: 0, right: 0,
                    display: 'flex', alignItems: 'center', gap: 5,
                    padding: '5px 10px', fontSize: t.font.size.sm, cursor: 'pointer', borderRadius: t.radius.sm,
                    border: `1px solid ${t.color.border}`, background: copied ? t.color.successLight : t.color.bgPage,
                    color: copied ? t.color.successText : t.color.textSecondary, transition: 'all 0.15s', fontWeight: t.font.weight.medium,
                  }}>
                    {copied
                      ? <><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M20 6L9 17l-5-5"/></svg>Copied!</>
                      : <><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/></svg>Copy</>
                    }
                  </button>
                  <MarkdownView content={results.analysis_md} />
                  {/* Sources collapsible */}
                  <div style={{ marginTop: 32 }}>
                    <button
                      onClick={() => setSourcesOpen(o => !o)}
                      style={{
                        display: 'flex', alignItems: 'center', gap: 6,
                        background: 'none', border: `1px solid ${t.color.border}`, borderRadius: 7,
                        padding: '7px 14px', fontSize: t.font.size.md, color: t.color.textSecondary, cursor: 'pointer',
                        transition: 'background 0.15s ease',
                      }}>
                      {sourcesOpen ? '▾' : '▸'} Sources ({results.sources_json?.length ?? 0})
                    </button>
                    {sourcesOpen && (
                      <div style={{ marginTop: 12 }}>
                        <SourcesView sources={results.sources_json ?? []} />
                      </div>
                    )}
                  </div>
                </div>
              )}
              {tab === 'simulation' && (
                <div>
                  {/* Verdict + metrics cards */}
                  <ReportView report={results.report_json} noDetails />
                  <PlatformComparison
                    posts={results.posts_json}
                    personas={results.personas_json}
                  />
                  <SimulationAnalytics
                    posts={results.posts_json}
                    report={results.report_json}
                    roundStats={roundStats}
                    personas={results.personas_json}
                    segmentDistribution={mergedSegmentDist}
                  />
                  {/* Segment Reactions + full analysis */}
                  <ReportView report={results.report_json} noSummary />
                  {/* Round filter */}
                  {maxRound > 0 && (
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 24, marginBottom: 12 }}>
                      <label htmlFor="result-round-filter" style={{ fontSize: t.font.size.sm, color: t.color.textSecondary, fontWeight: t.font.weight.semibold, flexShrink: 0 }}>
                        Round:
                      </label>
                      <select
                        id="result-round-filter"
                        value={selectedRound}
                        onChange={e => setSelectedRound(Number(e.target.value))}
                        style={{
                          fontSize: t.font.size.sm, padding: `${t.space[1]} ${t.space[2]}`, borderRadius: t.radius.sm,
                          border: `1px solid ${t.color.border}`, background: t.color.bgPage, color: t.color.textPrimary,
                          cursor: 'pointer',
                        }}
                      >
                        <option value={0}>All Rounds</option>
                        {Array.from({ length: maxRound }, (_, i) => i + 1).map(r => (
                          <option key={r} value={r}>Round {r}</option>
                        ))}
                      </select>
                    </div>
                  )}
                  <div style={{ marginTop: maxRound > 0 ? 0 : 24 }}>
                    <TopPosts posts={filteredPostsByPlatform} personasMap={personasMap} />
                  </div>
                </div>
              )}
              {tab === 'launch' && (
                <div style={{ position: 'relative' }}>
                  <button onClick={handleCopy} style={{
                    position: 'absolute', top: 0, right: 0,
                    display: 'flex', alignItems: 'center', gap: 5,
                    padding: '5px 10px', fontSize: t.font.size.sm, cursor: 'pointer', borderRadius: t.radius.sm,
                    border: `1px solid ${t.color.border}`, background: copied ? t.color.successLight : t.color.bgPage,
                    color: copied ? t.color.successText : t.color.textSecondary, transition: 'all 0.15s', fontWeight: t.font.weight.medium,
                  }}>
                    {copied
                      ? <><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M20 6L9 17l-5-5"/></svg>Copied!</>
                      : <><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/></svg>Copy</>
                    }
                  </button>
                  <MarkdownView content={results.gtm_md || '_Launch strategy not yet available._'} />
                </div>
              )}
              {tab === 'final' && (
                <div style={{ position: 'relative' }}>
                  <button onClick={handleCopy} style={{
                    position: 'absolute', top: 0, right: 0,
                    display: 'flex', alignItems: 'center', gap: 5,
                    padding: '5px 10px', fontSize: t.font.size.sm, cursor: 'pointer', borderRadius: t.radius.sm,
                    border: `1px solid ${t.color.border}`, background: copied ? t.color.successLight : t.color.bgPage,
                    color: copied ? t.color.successText : t.color.textSecondary, transition: 'all 0.15s', fontWeight: t.font.weight.medium,
                  }}>
                    {copied
                      ? <><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M20 6L9 17l-5-5"/></svg>Copied!</>
                      : <><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/></svg>Copy</>
                    }
                  </button>
                  <MarkdownView content={results.final_report_md || '_Final report not yet available._'} />
                </div>
              )}
              {tab === 'details' && (
                <DetailsView
                  posts={results.posts_json}
                  personas={results.personas_json}
                  allPosts={Object.values(results.posts_json).flatMap(list => list ?? [])}
                  reportJson={results.report_json ?? undefined}
                />
              )}
            </div>
          </>
        )}
      </main>
    </div>
  )
}
