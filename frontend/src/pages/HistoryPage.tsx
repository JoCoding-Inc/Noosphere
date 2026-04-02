import { useEffect, useState, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { Header } from '../components/Header'
import { getHistory, cancelSimulation, deleteSimulation } from '../api'
import type { HistoryItem } from '../types'

function getVerdictStyle(verdict: string): { background: string; color: string } {
  const v = verdict.toLowerCase()
  if (v === 'positive') return { background: '#dcfce7', color: '#15803d' }
  if (v === 'mixed') return { background: '#fef3c7', color: '#b45309' }
  if (v === 'skeptical') return { background: '#ffedd5', color: '#c2410c' }
  if (v === 'negative') return { background: '#fee2e2', color: '#b91c1c' }
  return { background: '#f1f5f9', color: '#475569' }
}

const STATUS_CONFIG = {
  completed: { color: '#22c55e', label: 'Done' },
  running: { color: '#f59e0b', label: 'Running' },
  failed: { color: '#ef4444', label: 'Failed' },
  partial: { color: '#f97316', label: 'Partial' },
}

export function HistoryPage() {
  const navigate = useNavigate()
  const [items, setItems] = useState<HistoryItem[]>([])
  const [loading, setLoading] = useState(true)
  const [cancellingIds, setCancellingIds] = useState<Record<string, boolean>>({})
  const [cancelErrors, setCancelErrors] = useState<Record<string, string>>({})
  const [deletingIds, setDeletingIds] = useState<Record<string, boolean>>({})
  const [searchQuery, setSearchQuery] = useState<string>('')
  const [filterVerdict, setFilterVerdict] = useState<string>('all')

  const filteredHistory = useMemo(() => {
    return items.filter(item => {
      const matchSearch = !searchQuery ||
        item.input_text_snippet.toLowerCase().includes(searchQuery.toLowerCase()) ||
        item.domain?.toLowerCase().includes(searchQuery.toLowerCase())
      const matchVerdict = filterVerdict === 'all' || item.verdict === filterVerdict
      return matchSearch && matchVerdict
    })
  }, [items, searchQuery, filterVerdict])

  useEffect(() => {
    getHistory()
      .then(setItems)
      .finally(() => setLoading(false))
  }, [])

  const handleCancel = async (e: React.MouseEvent, simId: string) => {
    e.stopPropagation()
    setCancellingIds(prev => ({ ...prev, [simId]: true }))
    setCancelErrors(prev => {
      if (!(simId in prev)) return prev
      const next = { ...prev }
      delete next[simId]
      return next
    })
    try {
      await cancelSimulation(simId)
      setItems(prev => prev.map(it => it.id === simId ? { ...it, status: 'failed' } : it))
      setCancelErrors(prev => {
        if (!(simId in prev)) return prev
        const next = { ...prev }
        delete next[simId]
        return next
      })
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to cancel simulation'
      setCancelErrors(prev => ({ ...prev, [simId]: message }))
    } finally {
      setCancellingIds(prev => {
        if (!(simId in prev)) return prev
        const next = { ...prev }
        delete next[simId]
        return next
      })
    }
  }

  const handleDelete = async (e: React.MouseEvent, item: HistoryItem) => {
    e.stopPropagation()
    const confirmed = window.confirm(
      `"${item.input_text_snippet}…"\n\n이 시뮬레이션을 완전히 삭제할까요? 복구할 수 없습니다.`
    )
    if (!confirmed) return
    setDeletingIds(prev => ({ ...prev, [item.id]: true }))
    try {
      await deleteSimulation(item.id)
      setItems(prev => prev.filter(it => it.id !== item.id))
    } finally {
      setDeletingIds(prev => {
        const next = { ...prev }
        delete next[item.id]
        return next
      })
    }
  }

  return (
    <div style={{ minHeight: '100vh', background: '#fafafa' }}>
      <Header />
      <main style={{ maxWidth: 800, margin: '0 auto', padding: '32px 24px' }}>
        <h1 style={{ fontSize: 24, fontWeight: 700, marginBottom: 24 }}>Simulation History</h1>

        {/* Search & Filter */}
        <div style={{ display: 'flex', gap: 10, marginBottom: 20, alignItems: 'center' }}>
          <input
            type="text"
            placeholder="Search by keyword or domain..."
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
            style={{
              flex: 1, padding: '8px 12px', fontSize: 13, borderRadius: 8,
              border: '1px solid #e2e8f0', background: '#fff', color: '#1e293b',
              outline: 'none', transition: 'border-color 0.15s',
            }}
            onFocus={e => (e.currentTarget.style.borderColor = '#6366f1')}
            onBlur={e => (e.currentTarget.style.borderColor = '#e2e8f0')}
          />
          <select
            value={filterVerdict}
            onChange={e => setFilterVerdict(e.target.value)}
            style={{
              padding: '8px 12px', fontSize: 13, borderRadius: 8,
              border: '1px solid #e2e8f0', background: '#fff', color: '#1e293b',
              cursor: 'pointer',
            }}
          >
            <option value="all">All Verdicts</option>
            <option value="positive">Positive</option>
            <option value="mixed">Mixed</option>
            <option value="skeptical">Skeptical</option>
            <option value="negative">Negative</option>
          </select>
        </div>

        {loading && <p style={{ color: '#64748b' }}>Loading...</p>}
        {!loading && items.length === 0 && (
          <p style={{ color: '#64748b' }}>No simulations yet. <a href="/app">Run one →</a></p>
        )}
        {!loading && items.length > 0 && filteredHistory.length === 0 && (
          <p style={{ color: '#94a3b8', fontSize: 13 }}>No results matching your search.</p>
        )}

        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {filteredHistory.map(item => {
            const status = STATUS_CONFIG[item.status] || STATUS_CONFIG.failed
            const date = new Date(item.created_at).toLocaleDateString()

            return (
              <div
                key={item.id}
                onClick={() => {
                  if (item.status === 'completed' || item.status === 'partial') navigate(`/result/${item.id}`)
                  else if (item.status === 'running' || item.status === 'failed') navigate(`/simulate/${item.id}`)
                }}
                style={{
                  padding: 16, borderRadius: 8, border: '1px solid #e2e8f0',
                  background: '#fff', cursor: 'pointer',
                  transition: 'border-color 0.15s',
                }}
                onMouseEnter={e => {
                  (e.currentTarget as HTMLDivElement).style.borderColor = '#1e293b'
                }}
                onMouseLeave={e => {
                  (e.currentTarget as HTMLDivElement).style.borderColor = '#e2e8f0'
                }}
              >
                <div className="history-item-row" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 12 }}>
                  <p style={{ margin: 0, fontSize: 15, fontWeight: 500, color: '#1e293b', flex: 1 }}>
                    {item.input_text_snippet}…
                  </p>
                  <div className="history-item-actions" style={{ display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0 }}>
                    {item.status === 'running' && (
                      <>
                        <button
                          onClick={e => handleCancel(e, item.id)}
                          disabled={Boolean(cancellingIds[item.id])}
                          style={{
                            fontSize: 11, padding: '3px 10px', borderRadius: 8,
                            border: '1px solid #fca5a5', background: '#fff',
                            color: '#ef4444', cursor: 'pointer', fontWeight: 600,
                            opacity: cancellingIds[item.id] ? 0.5 : 1,
                            transition: 'all 0.15s',
                          }}
                        >
                          {cancellingIds[item.id] ? 'Stopping...' : '■ Stop'}
                        </button>
                        {cancelErrors[item.id] && (
                          <span style={{ fontSize: 11, color: '#ef4444' }}>
                            {cancelErrors[item.id]}
                          </span>
                        )}
                      </>
                    )}
                    <span style={{
                      fontSize: 11, padding: '2px 8px', borderRadius: 10,
                      background: `${status.color}20`, color: status.color,
                      whiteSpace: 'nowrap',
                    }}>{status.label}</span>
                    {item.status !== 'running' && (
                      <button
                        onClick={e => handleDelete(e, item)}
                        disabled={Boolean(deletingIds[item.id])}
                        style={{
                          fontSize: 11, padding: '3px 8px', borderRadius: 8,
                          border: '1px solid #e2e8f0', background: '#fff',
                          color: '#94a3b8', cursor: 'pointer',
                          opacity: deletingIds[item.id] ? 0.5 : 1,
                          transition: 'all 0.15s',
                        }}
                        onMouseEnter={e => {
                          (e.currentTarget as HTMLButtonElement).style.borderColor = '#fca5a5'
                          ;(e.currentTarget as HTMLButtonElement).style.color = '#ef4444'
                        }}
                        onMouseLeave={e => {
                          (e.currentTarget as HTMLButtonElement).style.borderColor = '#e2e8f0'
                          ;(e.currentTarget as HTMLButtonElement).style.color = '#94a3b8'
                        }}
                      >
                        {deletingIds[item.id] ? '...' : '🗑'}
                      </button>
                    )}
                  </div>
                </div>
                <div style={{ display: 'flex', gap: 16, marginTop: 8, fontSize: 12, color: '#94a3b8', alignItems: 'center' }}>
                  <span>{date}</span>
                  <span>{item.language}</span>
                  {item.domain && <span>{item.domain}</span>}
                  {item.verdict && (() => {
                    const vs = getVerdictStyle(item.verdict)
                    return (
                      <span style={{
                        fontSize: 11, padding: '1px 7px', borderRadius: 8,
                        background: vs.background, color: vs.color, fontWeight: 600,
                      }}>
                        {item.verdict}
                      </span>
                    )
                  })()}
                  {item.evidence_count != null && (
                    <span style={{ fontSize: 11, color: '#94a3b8' }}>
                      {item.evidence_count} evidence
                    </span>
                  )}
                  {item.adoption_score != null && (
                    <span style={{
                      fontSize: 11, padding: '1px 8px', borderRadius: 8,
                      background: item.adoption_score >= 70 ? '#dcfce7' : item.adoption_score >= 40 ? '#fef3c7' : '#fee2e2',
                      color: item.adoption_score >= 70 ? '#15803d' : item.adoption_score >= 40 ? '#b45309' : '#b91c1c',
                      fontWeight: 600,
                    }}>
                      {item.adoption_score} pts
                    </span>
                  )}
                  {item.max_agents != null && (
                    <span style={{ fontSize: 11, color: '#94a3b8' }}>
                      {item.max_agents} agents
                    </span>
                  )}
                  {item.num_rounds != null && (
                    <span style={{ fontSize: 11, color: '#94a3b8' }}>
                      {item.num_rounds}R
                    </span>
                  )}
                  {item.duration_seconds != null && (
                    <span style={{ fontSize: 11, color: '#94a3b8' }}>
                      {Math.floor(item.duration_seconds / 60)}m {Math.floor(item.duration_seconds % 60)}s
                    </span>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      </main>
    </div>
  )
}
