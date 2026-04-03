import { useEffect, useState, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { t } from '../tokens'
import { Header } from '../components/Header'
import { getHistory, cancelSimulation, deleteSimulation } from '../api'
import type { HistoryItem } from '../types'

function getVerdictStyle(verdict: string): { background: string; color: string } {
  const v = verdict.toLowerCase()
  if (v === 'positive') return { background: '#dcfce7', color: '#15803d' }
  if (v === 'mixed') return { background: '#fef3c7', color: '#b45309' }
  if (v === 'skeptical') return { background: '#ffedd5', color: '#c2410c' }
  if (v === 'negative') return { background: '#fee2e2', color: t.color.dangerDark }
  return { background: t.color.bgSubtle, color: t.color.textStrong }
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
      `"${item.input_text_snippet}…"\n\nPermanently delete this simulation? This cannot be undone.`
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
    <div style={{ minHeight: '100vh', background: t.color.bgBody }}>
      <Header />
      <main style={{ maxWidth: 800, margin: '0 auto', padding: `${t.space[8]} ${t.space[6]}` }}>
        <h1 style={{ fontSize: 24, fontWeight: t.font.weight.bold, marginBottom: t.space[6] }}>Simulation History</h1>

        {/* Search & Filter */}
        <div style={{ display: 'flex', gap: 10, marginBottom: 20, alignItems: 'center' }}>
          <input
            type="text"
            placeholder="Search by keyword or domain..."
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
            style={{
              flex: 1, padding: `${t.space[2]} ${t.space[3]}`, fontSize: t.font.size.md, borderRadius: t.radius.md,
              border: `1px solid ${t.color.border}`, background: t.color.bgPage, color: t.color.textPrimary,
              outline: 'none', transition: 'border-color 0.15s',
            }}
            onFocus={e => (e.currentTarget.style.borderColor = t.color.borderFocus)}
            onBlur={e => (e.currentTarget.style.borderColor = t.color.border)}
          />
          <select
            value={filterVerdict}
            onChange={e => setFilterVerdict(e.target.value)}
            style={{
              padding: `${t.space[2]} ${t.space[3]}`, fontSize: t.font.size.md, borderRadius: t.radius.md,
              border: `1px solid ${t.color.border}`, background: t.color.bgPage, color: t.color.textPrimary,
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

        {loading && <p style={{ color: t.color.textSecondary }}>Loading...</p>}
        {!loading && items.length === 0 && (
          <p style={{ color: t.color.textSecondary }}>No simulations yet. <a href="/app">Run one →</a></p>
        )}
        {!loading && items.length > 0 && filteredHistory.length === 0 && (
          <p style={{ color: t.color.textMuted, fontSize: t.font.size.md }}>No results matching your search.</p>
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
                  padding: t.space[4], borderRadius: t.radius.md, border: `1px solid ${t.color.border}`,
                  background: t.color.bgPage, cursor: 'pointer',
                  transition: 'border-color 0.15s',
                }}
                onMouseEnter={e => {
                  (e.currentTarget as HTMLDivElement).style.borderColor = t.color.textPrimary
                }}
                onMouseLeave={e => {
                  (e.currentTarget as HTMLDivElement).style.borderColor = t.color.border
                }}
              >
                <div className="history-item-row" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 12 }}>
                  <p style={{ margin: 0, fontSize: 15, fontWeight: t.font.weight.medium, color: t.color.textPrimary, flex: 1 }}>
                    {item.input_text_snippet}…
                  </p>
                  <div className="history-item-actions" style={{ display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0 }}>
                    {item.status === 'running' && (
                      <>
                        <button
                          onClick={e => handleCancel(e, item.id)}
                          disabled={Boolean(cancellingIds[item.id])}
                          style={{
                            fontSize: t.font.size.xs, padding: '3px 10px', borderRadius: t.radius.md,
                            border: `1px solid ${t.color.dangerBorder}`, background: t.color.bgPage,
                            color: t.color.danger, cursor: 'pointer', fontWeight: t.font.weight.semibold,
                            opacity: cancellingIds[item.id] ? 0.5 : 1,
                            transition: 'all 0.15s',
                          }}
                        >
                          {cancellingIds[item.id] ? 'Stopping...' : '■ Stop'}
                        </button>
                        {cancelErrors[item.id] && (
                          <span style={{ fontSize: t.font.size.xs, color: t.color.danger }}>
                            {cancelErrors[item.id]}
                          </span>
                        )}
                      </>
                    )}
                    <span style={{
                      fontSize: t.font.size.xs, padding: '2px 8px', borderRadius: 10,
                      background: `${status.color}20`, color: status.color,
                      whiteSpace: 'nowrap',
                    }}>{status.label}</span>
                    {item.status !== 'running' && (
                      <button
                        onClick={e => handleDelete(e, item)}
                        disabled={Boolean(deletingIds[item.id])}
                        style={{
                          fontSize: t.font.size.xs, padding: '3px 8px', borderRadius: t.radius.md,
                          border: `1px solid ${t.color.border}`, background: t.color.bgPage,
                          color: t.color.textMuted, cursor: 'pointer',
                          opacity: deletingIds[item.id] ? 0.5 : 1,
                          transition: 'all 0.15s',
                        }}
                        onMouseEnter={e => {
                          (e.currentTarget as HTMLButtonElement).style.borderColor = t.color.dangerBorder
                          ;(e.currentTarget as HTMLButtonElement).style.color = t.color.danger
                        }}
                        onMouseLeave={e => {
                          (e.currentTarget as HTMLButtonElement).style.borderColor = t.color.border
                          ;(e.currentTarget as HTMLButtonElement).style.color = t.color.textMuted
                        }}
                      >
                        {deletingIds[item.id] ? '...' : '🗑'}
                      </button>
                    )}
                  </div>
                </div>
                <div style={{ display: 'flex', gap: 16, marginTop: t.space[2], fontSize: t.font.size.sm, color: t.color.textMuted, alignItems: 'center' }}>
                  <span>{date}</span>
                  <span>{item.language}</span>
                  {item.domain && <span>{item.domain}</span>}
                  {item.verdict && (() => {
                    const vs = getVerdictStyle(item.verdict)
                    return (
                      <span style={{
                        fontSize: t.font.size.xs, padding: '1px 7px', borderRadius: t.radius.md,
                        background: vs.background, color: vs.color, fontWeight: t.font.weight.semibold,
                      }}>
                        {item.verdict}
                      </span>
                    )
                  })()}
                  {item.evidence_count != null && (
                    <span style={{ fontSize: t.font.size.xs, color: t.color.textMuted }}>
                      {item.evidence_count} evidence
                    </span>
                  )}
                  {item.adoption_score != null && (
                    <span style={{
                      fontSize: t.font.size.xs, padding: '1px 8px', borderRadius: t.radius.md,
                      background: item.adoption_score >= 70 ? '#dcfce7' : item.adoption_score >= 40 ? '#fef3c7' : '#fee2e2',
                      color: item.adoption_score >= 70 ? '#15803d' : item.adoption_score >= 40 ? '#b45309' : t.color.dangerDark,
                      fontWeight: t.font.weight.semibold,
                    }}>
                      {item.adoption_score} pts
                    </span>
                  )}
                  {item.max_agents != null && (
                    <span style={{ fontSize: t.font.size.xs, color: t.color.textMuted }}>
                      {item.max_agents} agents
                    </span>
                  )}
                  {item.num_rounds != null && (
                    <span style={{ fontSize: t.font.size.xs, color: t.color.textMuted }}>
                      {item.num_rounds}R
                    </span>
                  )}
                  {item.duration_seconds != null && (
                    <span style={{ fontSize: t.font.size.xs, color: t.color.textMuted }}>
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
