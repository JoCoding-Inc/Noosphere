import { useEffect, useState, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
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
  running:   { color: '#f59e0b', label: 'Running' },
  failed:    { color: '#ef4444', label: 'Failed' },
  partial:   { color: '#f97316', label: 'Partial' },
}

interface Props {
  open: boolean
  onClose: () => void
}

export function HistorySidebar({ open, onClose }: Props) {
  const navigate = useNavigate()
  const [items, setItems] = useState<HistoryItem[]>([])
  const [loading, setLoading] = useState(false)
  const [cancellingIds, setCancellingIds] = useState<Record<string, boolean>>({})
  const [cancelErrors, setCancelErrors] = useState<Record<string, string>>({})
  const [deletingIds, setDeletingIds] = useState<Record<string, boolean>>({})
  const [searchQuery, setSearchQuery] = useState('')

  const filteredItems = useMemo(() => {
    if (!searchQuery) return items
    const q = searchQuery.toLowerCase()
    return items.filter(item =>
      item.input_text_snippet.toLowerCase().includes(q) ||
      item.domain?.toLowerCase().includes(q)
    )
  }, [items, searchQuery])

  useEffect(() => {
    if (!open) return
    setLoading(true)
    getHistory()
      .then(setItems)
      .finally(() => setLoading(false))
  }, [open])

  const handleCancel = async (e: React.MouseEvent, simId: string) => {
    e.stopPropagation()
    setCancellingIds(prev => ({ ...prev, [simId]: true }))
    setCancelErrors(prev => { const next = { ...prev }; delete next[simId]; return next })
    try {
      await cancelSimulation(simId)
      setItems(prev => prev.map(it => it.id === simId ? { ...it, status: 'failed' } : it))
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to cancel simulation'
      setCancelErrors(prev => ({ ...prev, [simId]: message }))
    } finally {
      setCancellingIds(prev => { const next = { ...prev }; delete next[simId]; return next })
    }
  }

  const handleDelete = async (e: React.MouseEvent, item: HistoryItem) => {
    e.stopPropagation()
    const confirmed = window.confirm(
      `"${item.input_text_snippet}…"\n\n이 시뮬레이션을 삭제할까요? 복구할 수 없습니다.`
    )
    if (!confirmed) return
    setDeletingIds(prev => ({ ...prev, [item.id]: true }))
    try {
      await deleteSimulation(item.id)
      setItems(prev => prev.filter(it => it.id !== item.id))
    } finally {
      setDeletingIds(prev => { const next = { ...prev }; delete next[item.id]; return next })
    }
  }

  return (
    <>
      {/* Backdrop */}
      <div
        onClick={onClose}
        style={{
          position: 'fixed', inset: 0, zIndex: 40,
          background: 'rgba(15,23,42,0.25)',
          opacity: open ? 1 : 0,
          pointerEvents: open ? 'auto' : 'none',
          transition: 'opacity 0.25s',
        }}
      />

      {/* Drawer */}
      <div style={{
        position: 'fixed', top: 0, right: 0, bottom: 0, zIndex: 50,
        width: 420, maxWidth: '90vw',
        background: '#fff',
        borderLeft: '1px solid #e2e8f0',
        boxShadow: '-4px 0 24px rgba(15,23,42,0.08)',
        transform: open ? 'translateX(0)' : 'translateX(100%)',
        transition: 'transform 0.28s cubic-bezier(0.4,0,0.2,1)',
        display: 'flex', flexDirection: 'column',
        overflowY: 'auto',
      }}>
        {/* Header */}
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '16px 20px',
          borderBottom: '1px solid #f1f5f9',
          position: 'sticky', top: 0, background: '#fff', zIndex: 1,
        }}>
          <span style={{ fontSize: 14, fontWeight: 600, color: '#1e293b' }}>History</span>
          <button
            onClick={onClose}
            style={{
              background: 'none', border: 'none', cursor: 'pointer',
              color: '#94a3b8', fontSize: 18, lineHeight: 1,
              padding: '2px 6px', borderRadius: 4,
              transition: 'color 0.15s',
            }}
            onMouseEnter={e => (e.currentTarget.style.color = '#1e293b')}
            onMouseLeave={e => (e.currentTarget.style.color = '#94a3b8')}
          >
            ✕
          </button>
        </div>

        {/* Content */}
        <div style={{ padding: '16px 20px', flex: 1 }}>
          {/* Search */}
          <div style={{ marginBottom: 12 }}>
            <input
              type="text"
              placeholder="Search..."
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              style={{
                width: '100%', padding: '6px 10px', fontSize: 12, borderRadius: 6,
                border: '1px solid #e2e8f0', background: '#f8fafc', color: '#1e293b',
                outline: 'none', boxSizing: 'border-box',
              }}
              onFocus={e => (e.currentTarget.style.borderColor = '#6366f1')}
              onBlur={e => (e.currentTarget.style.borderColor = '#e2e8f0')}
            />
          </div>

          {loading && <p style={{ color: '#94a3b8', fontSize: 13 }}>Loading...</p>}
          {!loading && items.length === 0 && (
            <p style={{ color: '#94a3b8', fontSize: 13 }}>No simulations yet.</p>
          )}
          {!loading && items.length > 0 && filteredItems.length === 0 && (
            <p style={{ color: '#94a3b8', fontSize: 12 }}>No matching results.</p>
          )}

          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {filteredItems.map(item => {
              const status = STATUS_CONFIG[item.status] || STATUS_CONFIG.failed
              const date = new Date(item.created_at).toLocaleDateString()

              return (
                <div
                  key={item.id}
                  onClick={() => {
                    if (item.status === 'completed' || item.status === 'partial') {
                      onClose()
                      navigate(`/result/${item.id}`)
                    }
                  }}
                  style={{
                    padding: '12px 14px', borderRadius: 8,
                    border: '1px solid #e2e8f0', background: '#fff',
                    cursor: item.status === 'completed' || item.status === 'partial' ? 'pointer' : 'default',
                    transition: 'border-color 0.15s',
                  }}
                  onMouseEnter={e => {
                    if (item.status === 'completed' || item.status === 'partial')
                      (e.currentTarget as HTMLDivElement).style.borderColor = '#1e293b'
                  }}
                  onMouseLeave={e => {
                    (e.currentTarget as HTMLDivElement).style.borderColor = '#e2e8f0'
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 8 }}>
                    <p style={{ margin: 0, fontSize: 13, fontWeight: 500, color: '#1e293b', flex: 1, lineHeight: 1.5 }}>
                      {item.input_text_snippet}…
                    </p>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexShrink: 0 }}>
                      {item.status === 'running' && (
                        <>
                          <button
                            onClick={e => handleCancel(e, item.id)}
                            disabled={Boolean(cancellingIds[item.id])}
                            style={{
                              fontSize: 11, padding: '2px 8px', borderRadius: 6,
                              border: '1px solid #fca5a5', background: '#fff',
                              color: '#ef4444', cursor: 'pointer', fontWeight: 600,
                              opacity: cancellingIds[item.id] ? 0.5 : 1,
                            }}
                          >
                            {cancellingIds[item.id] ? 'Stopping...' : '■ Stop'}
                          </button>
                          {cancelErrors[item.id] && (
                            <span style={{ fontSize: 11, color: '#ef4444' }}>{cancelErrors[item.id]}</span>
                          )}
                        </>
                      )}
                      <span style={{
                        fontSize: 11, padding: '2px 7px', borderRadius: 10,
                        background: `${status.color}20`, color: status.color,
                        whiteSpace: 'nowrap',
                      }}>{status.label}</span>
                      {item.status !== 'running' && (
                        <button
                          onClick={e => handleDelete(e, item)}
                          disabled={Boolean(deletingIds[item.id])}
                          style={{
                            fontSize: 11, padding: '2px 7px', borderRadius: 6,
                            border: '1px solid #e2e8f0', background: '#fff',
                            color: '#94a3b8', cursor: 'pointer',
                            opacity: deletingIds[item.id] ? 0.5 : 1,
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
                  <div style={{ display: 'flex', gap: 12, marginTop: 6, fontSize: 11, color: '#94a3b8', alignItems: 'center' }}>
                    <span>{date}</span>
                    <span>{item.language}</span>
                    {item.domain && (
                      <span style={{
                        fontSize: 10, padding: '1px 7px', borderRadius: 8,
                        background: '#ede9fe', color: '#7c3aed', fontWeight: 600,
                      }}>
                        {item.domain}
                      </span>
                    )}
                    {item.verdict && (() => {
                      const vs = getVerdictStyle(item.verdict)
                      return (
                        <span style={{
                          fontSize: 10, padding: '1px 6px', borderRadius: 8,
                          background: vs.background, color: vs.color, fontWeight: 600,
                        }}>
                          {item.verdict}
                        </span>
                      )
                    })()}
                    {item.evidence_count != null && (
                      <span style={{ fontSize: 10, color: '#94a3b8' }}>
                        {item.evidence_count} evidence
                      </span>
                    )}
                    {item.adoption_score != null && (
                      <span style={{
                        fontSize: 10, padding: '1px 6px', borderRadius: 8,
                        background: item.adoption_score >= 70 ? '#dcfce7' : item.adoption_score >= 40 ? '#fef3c7' : '#fee2e2',
                        color: item.adoption_score >= 70 ? '#15803d' : item.adoption_score >= 40 ? '#b45309' : '#b91c1c',
                        fontWeight: 600,
                      }}>
                        {item.adoption_score} pts
                      </span>
                    )}
                    {item.max_agents != null && (
                      <span style={{ fontSize: 10, color: '#94a3b8' }}>
                        {item.max_agents} agents
                      </span>
                    )}
                    {item.num_rounds != null && (
                      <span style={{ fontSize: 10, color: '#94a3b8' }}>
                        {item.num_rounds}R
                      </span>
                    )}
                    {item.duration_seconds != null && (
                      <span style={{ fontSize: 10, color: '#94a3b8' }}>
                        {Math.floor(item.duration_seconds / 60)}m {Math.floor(item.duration_seconds % 60)}s
                      </span>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      </div>
    </>
  )
}
