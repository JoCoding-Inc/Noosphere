import { useEffect, useState, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { getHistory, cancelSimulation, deleteSimulation } from '../api'
import type { HistoryItem } from '../types'
import { t } from '../tokens'

function getVerdictStyle(verdict: string): { background: string; color: string } {
  const v = verdict.toLowerCase()
  if (v === 'positive') return { background: t.color.successSurface, color: t.color.successText }
  if (v === 'mixed') return { background: t.color.warningSubtle, color: t.color.warningDark }
  if (v === 'skeptical') return { background: t.color.warningSurface, color: t.color.warningStrong }
  if (v === 'negative') return { background: t.color.dangerSurface, color: t.color.dangerDark }
  return { background: t.color.bgSubtle, color: t.color.textStrong }
}

const STATUS_CONFIG = {
  completed: { color: t.color.success, label: 'Done' },
  running:   { color: t.color.warning, label: 'Running' },
  failed:    { color: t.color.danger, label: 'Failed' },
  partial:   { color: t.color.orange, label: 'Partial' },
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
      `"${item.input_text_snippet}…"\n\nDelete this simulation? This cannot be undone.`
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
        background: t.color.bgPage,
        borderLeft: `1px solid ${t.color.border}`,
        boxShadow: '-4px 0 24px rgba(15,23,42,0.08)',
        transform: open ? 'translateX(0)' : 'translateX(100%)',
        transition: 'transform 0.28s cubic-bezier(0.4,0,0.2,1)',
        display: 'flex', flexDirection: 'column',
        overflowY: 'auto',
      }}>
        {/* Header */}
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: `${t.space[4]}px ${t.space[5]}px`,
          borderBottom: `1px solid ${t.color.bgSubtle}`,
          position: 'sticky', top: 0, background: t.color.bgPage, zIndex: 1,
        }}>
          <span style={{ fontSize: t.font.size.lg, fontWeight: t.font.weight.semibold, color: t.color.textPrimary }}>History</span>
          <button
            onClick={onClose}
            style={{
              background: 'none', border: 'none', cursor: 'pointer',
              color: t.color.textMuted, fontSize: 18, lineHeight: 1,
              padding: '2px 6px', borderRadius: 4,
              transition: 'color 0.15s',
            }}
            onMouseEnter={e => (e.currentTarget.style.color = t.color.textPrimary)}
            onMouseLeave={e => (e.currentTarget.style.color = t.color.textMuted)}
          >
            ✕
          </button>
        </div>

        {/* Content */}
        <div style={{ padding: `${t.space[4]}px ${t.space[5]}px`, flex: 1 }}>
          {/* Search */}
          <div style={{ marginBottom: t.space[3] }}>
            <input
              type="text"
              placeholder="Search..."
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              style={{
                width: '100%', padding: '6px 10px', fontSize: t.font.size.sm, borderRadius: t.radius.sm,
                border: `1px solid ${t.color.border}`, background: t.color.bgCard, color: t.color.textPrimary,
                outline: 'none', boxSizing: 'border-box',
              }}
              onFocus={e => (e.currentTarget.style.borderColor = t.color.borderFocus)}
              onBlur={e => (e.currentTarget.style.borderColor = t.color.border)}
            />
          </div>

          {loading && <p style={{ color: t.color.textMuted, fontSize: t.font.size.md }}>Loading...</p>}
          {!loading && items.length === 0 && (
            <p style={{ color: t.color.textMuted, fontSize: t.font.size.md }}>No simulations yet.</p>
          )}
          {!loading && items.length > 0 && filteredItems.length === 0 && (
            <p style={{ color: t.color.textMuted, fontSize: t.font.size.sm }}>No matching results.</p>
          )}

          <div style={{ display: 'flex', flexDirection: 'column', gap: t.space[2] }}>
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
                    padding: `${t.space[3]}px ${t.space[3]}px`, borderRadius: t.radius.md,
                    border: `1px solid ${t.color.border}`, background: t.color.bgPage,
                    cursor: item.status === 'completed' || item.status === 'partial' ? 'pointer' : 'default',
                    transition: 'border-color 0.15s',
                  }}
                  onMouseEnter={e => {
                    if (item.status === 'completed' || item.status === 'partial')
                      (e.currentTarget as HTMLDivElement).style.borderColor = t.color.textPrimary
                  }}
                  onMouseLeave={e => {
                    (e.currentTarget as HTMLDivElement).style.borderColor = t.color.border
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: t.space[2] }}>
                    <p style={{ margin: 0, fontSize: t.font.size.md, fontWeight: t.font.weight.medium, color: t.color.textPrimary, flex: 1, lineHeight: 1.5 }}>
                      {item.input_text_snippet}…
                    </p>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexShrink: 0 }}>
                      {item.status === 'running' && (
                        <>
                          <button
                            onClick={e => handleCancel(e, item.id)}
                            disabled={Boolean(cancellingIds[item.id])}
                            style={{
                              fontSize: t.font.size.xs, padding: '2px 8px', borderRadius: t.radius.sm,
                              border: `1px solid ${t.color.dangerBorder}`, background: t.color.bgPage,
                              color: t.color.danger, cursor: 'pointer', fontWeight: t.font.weight.semibold,
                              opacity: cancellingIds[item.id] ? 0.5 : 1,
                            }}
                          >
                            {cancellingIds[item.id] ? 'Stopping...' : '■ Stop'}
                          </button>
                          {cancelErrors[item.id] && (
                            <span style={{ fontSize: t.font.size.xs, color: t.color.danger }}>{cancelErrors[item.id]}</span>
                          )}
                        </>
                      )}
                      <span style={{
                        fontSize: t.font.size.xs, padding: '2px 7px', borderRadius: t.radius.lg,
                        background: `${status.color}20`, color: status.color,
                        whiteSpace: 'nowrap',
                      }}>{status.label}</span>
                      {item.status !== 'running' && (
                        <button
                          onClick={e => handleDelete(e, item)}
                          disabled={Boolean(deletingIds[item.id])}
                          style={{
                            fontSize: t.font.size.xs, padding: '2px 7px', borderRadius: t.radius.sm,
                            border: `1px solid ${t.color.border}`, background: t.color.bgPage,
                            color: t.color.textMuted, cursor: 'pointer',
                            opacity: deletingIds[item.id] ? 0.5 : 1,
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
                  <div style={{ display: 'flex', gap: t.space[3], marginTop: 6, fontSize: t.font.size.xs, color: t.color.textMuted, alignItems: 'center' }}>
                    <span>{date}</span>
                    <span>{item.language}</span>
                    {item.domain && (
                      <span style={{
                        fontSize: t.font.size.xs, padding: '1px 7px', borderRadius: t.radius.md,
                        background: t.color.accentLight, color: t.color.accentDark, fontWeight: t.font.weight.semibold,
                      }}>
                        {item.domain}
                      </span>
                    )}
                    {item.verdict && (() => {
                      const vs = getVerdictStyle(item.verdict)
                      return (
                        <span style={{
                          fontSize: t.font.size.xs, padding: '1px 6px', borderRadius: t.radius.md,
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
                        fontSize: t.font.size.xs, padding: '1px 6px', borderRadius: t.radius.md,
                        background: item.adoption_score >= 70 ? t.color.successSurface : item.adoption_score >= 40 ? t.color.warningSubtle : t.color.dangerSurface,
                        color: item.adoption_score >= 70 ? t.color.successText : item.adoption_score >= 40 ? t.color.warningDark : t.color.dangerDark,
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
        </div>
      </div>
    </>
  )
}
