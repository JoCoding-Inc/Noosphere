import type { ReportJSON } from '../types'

const VERDICT_CONFIG = {
  positive: { emoji: '✅', color: '#22c55e', label: 'Positive' },
  mixed: { emoji: '⚖️', color: '#f59e0b', label: 'Mixed' },
  skeptical: { emoji: '🤔', color: '#f97316', label: 'Skeptical' },
  negative: { emoji: '❌', color: '#ef4444', label: 'Negative' },
}

const SENTIMENT_ICONS: Record<string, string> = { positive: '👍', neutral: '😐', negative: '👎' }

export function ReportView({ report, simId }: { report: ReportJSON; simId: string }) {
  const API_BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'
  const v = VERDICT_CONFIG[report.verdict] || VERDICT_CONFIG.mixed

  return (
    <div>
      <div style={{
        padding: 20, borderRadius: 10, marginBottom: 24,
        border: `1px solid ${v.color}20`,
        background: `${v.color}08`,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 4 }}>
          <span style={{ fontSize: 24 }}>{v.emoji}</span>
          <span style={{ fontSize: 20, fontWeight: 700, color: v.color }}>{v.label}</span>
        </div>
        <p style={{ margin: 0, fontSize: 14, color: '#64748b' }}>
          Based on {report.evidence_count} simulated interactions
        </p>
      </div>

      <h3 style={{ fontSize: 16, fontWeight: 600, marginBottom: 12 }}>Segment Reactions</h3>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12, marginBottom: 24 }}>
        {report.segments.map(seg => (
          <div key={seg.name} style={{
            padding: 14, borderRadius: 8, border: '1px solid #e2e8f0', background: '#fff',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
              <span>{SENTIMENT_ICONS[seg.sentiment]}</span>
              <span style={{ fontWeight: 600, fontSize: 14 }}>
                {seg.name.replace('_', ' ').replace(/\b\w/g, c => c.toUpperCase())}
              </span>
            </div>
            <p style={{ margin: '0 0 8px', fontSize: 14, color: '#475569' }}>{seg.summary}</p>
            {seg.key_quotes.map((q, i) => (
              <p key={i} style={{
                margin: '4px 0', paddingLeft: 12, borderLeft: '3px solid #e2e8f0',
                fontSize: 13, color: '#64748b', fontStyle: 'italic',
              }}>"{q}"</p>
            ))}
          </div>
        ))}
      </div>

      <h3 style={{ fontSize: 16, fontWeight: 600, marginBottom: 12 }}>Criticism Patterns</h3>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 24 }}>
        {report.criticism_clusters.map((c, i) => (
          <div key={i} style={{
            padding: 12, borderRadius: 8, border: '1px solid #fecdd3',
            background: '#fff1f2',
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
              <span style={{ fontWeight: 600, fontSize: 14 }}>{c.theme}</span>
              <span style={{ fontSize: 12, color: '#94a3b8' }}>{c.count} mentions</span>
            </div>
            {c.examples.slice(0, 2).map((ex, j) => (
              <p key={j} style={{ margin: '2px 0', fontSize: 13, color: '#64748b' }}>
                — "{ex}"
              </p>
            ))}
          </div>
        ))}
      </div>

      <h3 style={{ fontSize: 16, fontWeight: 600, marginBottom: 12 }}>Improvement Suggestions</h3>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginBottom: 32 }}>
        {report.improvements.map((imp, i) => (
          <div key={i} style={{
            display: 'flex', justifyContent: 'space-between', alignItems: 'center',
            padding: '10px 14px', borderRadius: 8, border: '1px solid #d1fae5',
            background: '#f0fdf4',
          }}>
            <span style={{ fontSize: 14, color: '#1e293b' }}>{imp.suggestion}</span>
            <span style={{ fontSize: 12, color: '#94a3b8', whiteSpace: 'nowrap', marginLeft: 8 }}>
              ×{imp.frequency}
            </span>
          </div>
        ))}
      </div>

    </div>
  )
}
