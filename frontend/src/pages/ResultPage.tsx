import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Header } from '../components/Header'
import { ReportView } from '../components/ReportView'
import { DetailsView } from '../components/DetailsView'
import { MarkdownView } from '../components/MarkdownView'
import { SourcesView } from '../components/SourcesView'
import { getResults, exportPdfUrl } from '../api'
import { VERDICT_CONFIG } from '../constants'
import type { SimResults } from '../types'

type Tab = 'analysis' | 'simulation' | 'launch' | 'final' | 'details'

export function ResultPage() {
  const { simId } = useParams<{ simId: string }>()
  const navigate = useNavigate()
  const [results, setResults] = useState<SimResults | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [tab, setTab] = useState<Tab>('analysis')
  const [sourcesOpen, setSourcesOpen] = useState(false)

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

  const verdict = results?.report_json?.verdict
  const v = verdict ? (VERDICT_CONFIG[verdict] || VERDICT_CONFIG.mixed) : null

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
            {/* Verdict summary card — always visible */}
            {v && (
              <div className="result-verdict-card" style={{
                padding: '12px 18px', borderRadius: 10, marginBottom: 20,
                border: `1px solid ${v.color}30`, background: `${v.color}08`,
                display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                boxShadow: 'var(--shadow-card)',
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <svg
                    width="20" height="20" viewBox="0 0 24 24"
                    fill="none" stroke={v.color} strokeWidth="2"
                    aria-hidden="true"
                    style={{ flexShrink: 0 }}
                    dangerouslySetInnerHTML={{ __html: v.icon }}
                  />
                  <span style={{ fontSize: 16, fontWeight: 700, color: v.color }}>{v.label}</span>
                  <span style={{ fontSize: 13, color: '#94a3b8' }}>
                    · {results.report_json?.evidence_count ?? 0} interactions simulated
                  </span>
                </div>
                <a
                  href={exportPdfUrl(simId!)}
                  download
                  style={{
                    display: 'inline-block', padding: '6px 14px', background: '#6366f1',
                    color: '#fff', borderRadius: 7, textDecoration: 'none', fontSize: 12,
                    fontWeight: 600,
                  }}>
                  ↓ PDF
                </a>
              </div>
            )}

            {/* Tab navigation */}
            <div className="result-tabs" style={{ display: 'flex', gap: 4, marginBottom: 24, borderBottom: '1px solid #e2e8f0' }}>
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
                <ReportView report={results.report_json} />
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
                />
              )}
            </div>
          </>
        )}
      </main>
    </div>
  )
}
