import { useEffect, useMemo, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
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
        <span style={{ fontSize: 14, fontWeight: 700, color: '#6366f1' }}>Platform Comparison</span>
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
              background: '#fff', border: '1px solid #e2e8f0', borderRadius: 8,
              padding: 12, boxShadow: '0 1px 3px rgba(0,0,0,0.04)',
            }}>
              <div style={{ fontSize: 12, fontWeight: 700, color: '#1e293b', marginBottom: 6 }}>
                {PLATFORM_SHORT[platform] ?? platform}
              </div>
              <div style={{ fontSize: 20, fontWeight: 700, color: '#6366f1', marginBottom: 6 }}>
                {total}
                <span style={{ fontSize: 11, fontWeight: 400, color: '#94a3b8', marginLeft: 4 }}>posts</span>
              </div>
              {/* Sentiment mini-bar */}
              <div style={{ display: 'flex', height: 5, borderRadius: 3, overflow: 'hidden', background: '#e2e8f0', marginBottom: 6 }}>
                {posPct > 0 && <div style={{ width: `${posPct}%`, background: '#22c55e' }} />}
                {neuPct > 0 && <div style={{ width: `${neuPct}%`, background: '#94a3b8' }} />}
                {negPct > 0 && <div style={{ width: `${negPct}%`, background: '#ef4444' }} />}
                {conPct > 0 && <div style={{ width: `${conPct}%`, background: '#3b82f6' }} />}
              </div>
              <div style={{ display: 'flex', gap: 6, fontSize: 9, color: '#94a3b8', marginBottom: 6 }}>
                <span>{posPct}% pos</span>
                <span>{neuPct}% neu</span>
                <span>{negPct}% neg</span>
                {conPct > 0 && <span>{conPct}% con</span>}
              </div>
              {topName && (
                <div style={{ fontSize: 10, color: '#64748b', borderTop: '1px solid #f1f5f9', paddingTop: 4 }}>
                  Most active: <span style={{ fontWeight: 600, color: '#1e293b' }}>{topName}</span>
                  <span style={{ color: '#94a3b8' }}> ({topCount})</span>
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
    <div style={{ minHeight: '100vh', background: '#fafafa' }}>
      <Header />
      <main className="page-enter" style={{ maxWidth: 1280, margin: '0 auto', padding: '32px 24px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
          <button onClick={() => navigate('/app')}
            style={{ background: 'none', border: 'none', color: '#64748b', cursor: 'pointer', fontSize: 14 }}>
            ← New simulation
          </button>
        </div>

        {loading && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, color: '#64748b', fontSize: 14 }}>
            <span className="spinner" style={{ borderColor: 'rgba(100,116,139,0.3)', borderTopColor: '#64748b' }} />
            Loading results...
          </div>
        )}
        {error && <p role="alert" style={{ color: '#ef4444' }}>{error}</p>}

        {results && (
          <>
            {/* PDF download — always visible above tabs */}
            <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 12 }}>
              <a
                href={exportPdfUrl(simId ?? '')}
                download
                style={{
                  display: 'inline-block', padding: '8px 18px', background: '#6366f1',
                  color: '#fff', borderRadius: 8, textDecoration: 'none', fontSize: 13,
                  fontWeight: 600,
                }}>
                ↓ Download Report PDF
              </a>
            </div>
            {/* Tab navigation */}
            <div className="result-tabs" style={{ display: 'flex', alignItems: 'center', gap: 4, marginBottom: 24, borderBottom: '1px solid #e2e8f0' }}>
              {tabs.map(t => (
                <button key={t.id} onClick={() => setTab(t.id)}
                  style={{
                    padding: '10px 20px', fontSize: 14, cursor: 'pointer', border: 'none',
                    background: 'none', fontWeight: tab === t.id ? 600 : 400,
                    borderBottom: tab === t.id ? '2px solid #6366f1' : '2px solid transparent',
                    color: tab === t.id ? '#6366f1' : '#64748b',
                    transition: 'color 0.15s, border-color 0.15s',
                  }}>
                  {t.label}
                </button>
              ))}
              {copyableContent[tab] && (
                <button
                  onClick={handleCopy}
                  style={{
                    marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 5,
                    padding: '6px 12px', fontSize: 12, cursor: 'pointer', borderRadius: 6,
                    border: '1px solid #e2e8f0', background: copied ? '#f0fdf4' : '#fff',
                    color: copied ? '#16a34a' : '#64748b',
                    transition: 'all 0.15s', fontWeight: 500,
                  }}>
                  {copied ? (
                    <>
                      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M20 6L9 17l-5-5"/>
                      </svg>
                      Copied!
                    </>
                  ) : (
                    <>
                      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/>
                      </svg>
                      Copy
                    </>
                  )}
                </button>
              )}
            </div>

            <div key={tab} className="tab-content">
              {tab === 'analysis' && (
                <div>
                  <MarkdownView content={results.analysis_md} />
                  {/* Sources collapsible */}
                  <div style={{ marginTop: 32 }}>
                    <button
                      onClick={() => setSourcesOpen(o => !o)}
                      style={{
                        display: 'flex', alignItems: 'center', gap: 6,
                        background: 'none', border: '1px solid #e2e8f0', borderRadius: 7,
                        padding: '7px 14px', fontSize: 13, color: '#64748b', cursor: 'pointer',
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
                      <label htmlFor="result-round-filter" style={{ fontSize: 12, color: '#64748b', fontWeight: 600, flexShrink: 0 }}>
                        Round:
                      </label>
                      <select
                        id="result-round-filter"
                        value={selectedRound}
                        onChange={e => setSelectedRound(Number(e.target.value))}
                        style={{
                          fontSize: 12, padding: '4px 8px', borderRadius: 6,
                          border: '1px solid #e2e8f0', background: '#fff', color: '#1e293b',
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
                <MarkdownView content={results.gtm_md || '_Launch strategy not yet available._'} />
              )}
              {tab === 'final' && (
                <MarkdownView content={results.final_report_md || '_Final report not yet available._'} />
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
