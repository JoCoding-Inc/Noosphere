import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Header } from '../components/Header'
import { SocialFeedView } from '../components/SocialFeedView'
import { PersonaCardView } from '../components/PersonaCardView'
import { ReportView } from '../components/ReportView'
import { getResults } from '../api'
import { MarkdownView } from '../components/MarkdownView'
import type { SimResults } from '../types'

type Tab = 'analysis' | 'report' | 'feed' | 'personas'

export function ResultPage() {
  const { simId } = useParams<{ simId: string }>()
  const navigate = useNavigate()
  const [results, setResults] = useState<SimResults | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [tab, setTab] = useState<Tab>('analysis')

  useEffect(() => {
    if (!simId) return
    getResults(simId)
      .then(setResults)
      .catch(e => setError(e instanceof Error ? e.message : 'Unknown error'))
      .finally(() => setLoading(false))
  }, [simId])

  const API_BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

  const tabs: { id: Tab; label: string }[] = [
    { id: 'analysis', label: 'Analysis' },
    { id: 'report', label: 'Simulation' },
    { id: 'feed', label: 'Social Feed' },
    { id: 'personas', label: 'Personas' },
  ]

  return (
    <div style={{ minHeight: '100vh', background: '#fafafa' }}>
      <Header />
      <main className="page-enter" style={{ maxWidth: 900, margin: '0 auto', padding: '32px 24px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
          <button onClick={() => navigate('/')}
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
        {error && <p style={{ color: '#ef4444' }}>{error}</p>}

        {results && (
          <>
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
                href={`${API_BASE}/export/${simId}`}
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
                <MarkdownView content={results.analysis_md || '_분석 보고서 없음_'} />
              )}
              {tab === 'report' && (
                <ReportView report={results.report_json} simId={simId!} />
              )}
              {tab === 'feed' && (
                <SocialFeedView posts={results.posts_json} />
              )}
              {tab === 'personas' && (
                <PersonaCardView personas={results.personas_json} />
              )}
            </div>
          </>
        )}
      </main>
    </div>
  )
}
