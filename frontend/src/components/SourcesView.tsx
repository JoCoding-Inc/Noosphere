import { SOURCE_COLORS } from '../constants'
import { t } from '../tokens'
import type { SourceItem } from '../types'

interface Props {
  sources: SourceItem[]
}

export function SourcesView({ sources }: Props) {
  if (sources.length === 0) {
    return (
      <div style={{ textAlign: 'center', color: t.color.textMuted, fontSize: t.font.size.lg, padding: '48px 0' }}>
        No source items collected.
      </div>
    )
  }

  const sorted = [...sources].sort((a, b) => b.score - a.score)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: t.space[2] }}>
      <div style={{ fontSize: t.font.size.sm, color: t.color.textMuted, marginBottom: t.space[1] }}>
        {sources.length} items collected
      </div>
      {sorted.map(item => (
        <div
          key={item.id}
          style={{
            padding: '10px 14px',
            borderRadius: t.radius.md,
            background: t.color.bgPage,
            border: `1px solid ${t.color.border}`,
            borderLeft: `3px solid ${SOURCE_COLORS[item.source] || t.color.textMuted}`,
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: t.space[1] }}>
            <span style={{
              fontSize: t.font.size.xs, fontWeight: t.font.weight.bold, padding: '1px 6px', borderRadius: t.radius.md,
              background: SOURCE_COLORS[item.source] ? `${SOURCE_COLORS[item.source]}18` : t.color.bgSubtle,
              color: SOURCE_COLORS[item.source] || t.color.textSecondary,
              textTransform: 'uppercase', letterSpacing: '0.04em',
            }}>
              {item.source}
            </span>
            {item.score > 0 && (
              <span style={{ fontSize: t.font.size.xs, color: t.color.textMuted, fontVariantNumeric: 'tabular-nums' }}>
                {item.score.toFixed(1)}
              </span>
            )}
          </div>
          <div style={{ fontSize: t.font.size.md, fontWeight: t.font.weight.semibold, color: t.color.textPrimary, lineHeight: 1.4 }}>
            {item.url ? (
              <a href={item.url} target="_blank" rel="noopener noreferrer"
                style={{ color: t.color.textPrimary, textDecoration: 'none' }}
                onMouseEnter={e => (e.currentTarget.style.textDecoration = 'underline')}
                onMouseLeave={e => (e.currentTarget.style.textDecoration = 'none')}
              >
                {item.title}
              </a>
            ) : item.title}
          </div>
          {item.text && (
            <div style={{ fontSize: t.font.size.sm, color: t.color.textSecondary, marginTop: t.space[1], lineHeight: 1.5 }}>
              {item.text.slice(0, 140)}{item.text.length > 140 ? '…' : ''}
            </div>
          )}
        </div>
      ))}
    </div>
  )
}
