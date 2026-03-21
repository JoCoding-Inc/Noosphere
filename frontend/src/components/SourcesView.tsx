import { SOURCE_COLORS } from '../constants'
import type { SourceItem } from '../types'

interface Props {
  sources: SourceItem[]
}

export function SourcesView({ sources }: Props) {
  if (sources.length === 0) {
    return (
      <div style={{ textAlign: 'center', color: '#94a3b8', fontSize: 14, padding: '48px 0' }}>
        No source items collected.
      </div>
    )
  }

  const sorted = [...sources].sort((a, b) => b.score - a.score)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      <div style={{ fontSize: 12, color: '#94a3b8', marginBottom: 4 }}>
        {sources.length} items collected
      </div>
      {sorted.map(item => (
        <div
          key={item.id}
          style={{
            padding: '10px 14px',
            borderRadius: 8,
            background: '#fff',
            border: '1px solid #e2e8f0',
            borderLeft: `3px solid ${SOURCE_COLORS[item.source] || '#94a3b8'}`,
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 4 }}>
            <span style={{
              fontSize: 10, fontWeight: 700, padding: '1px 6px', borderRadius: 8,
              background: SOURCE_COLORS[item.source] ? `${SOURCE_COLORS[item.source]}18` : '#f1f5f9',
              color: SOURCE_COLORS[item.source] || '#64748b',
              textTransform: 'uppercase', letterSpacing: '0.04em',
            }}>
              {item.source}
            </span>
            <span style={{ fontSize: 11, color: '#94a3b8', fontVariantNumeric: 'tabular-nums' }}>
              {item.score.toFixed(1)}
            </span>
          </div>
          <div style={{ fontSize: 13, fontWeight: 600, color: '#1e293b', lineHeight: 1.4 }}>
            {item.url ? (
              <a href={item.url} target="_blank" rel="noopener noreferrer"
                style={{ color: '#1e293b', textDecoration: 'none' }}
                onMouseEnter={e => (e.currentTarget.style.textDecoration = 'underline')}
                onMouseLeave={e => (e.currentTarget.style.textDecoration = 'none')}
              >
                {item.title}
              </a>
            ) : item.title}
          </div>
          {item.text && (
            <div style={{ fontSize: 12, color: '#64748b', marginTop: 4, lineHeight: 1.5 }}>
              {item.text.slice(0, 140)}{item.text.length > 140 ? '…' : ''}
            </div>
          )}
        </div>
      ))}
    </div>
  )
}
