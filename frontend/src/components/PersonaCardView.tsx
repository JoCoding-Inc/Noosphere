import type { Persona, Platform } from '../types'

const PLATFORM_LABELS: Record<Platform, string> = {
  hackernews: 'HN',
  producthunt: 'PH',
  indiehackers: 'IH',
  reddit_startups: 'Reddit',
  linkedin: 'LinkedIn',
}

const BIAS_COLORS: Record<string, string> = {
  academic: '#6366f1',
  commercial: '#22c55e',
  skeptic: '#f59e0b',
  evangelist: '#ec4899',
}

type PersonaWithPlatform = Persona & { platform: Platform }

export function PersonaCardView({ personas }: { personas: Partial<Record<Platform, Persona[]>> | null | undefined }) {
  const allPersonas: PersonaWithPlatform[] = Object.entries(personas ?? {}).flatMap(([platform, list]) =>
    (list ?? []).map(p => ({ ...p, platform: platform as Platform }))
  )

  if (allPersonas.length === 0) {
    return (
      <div style={{ padding: 48, textAlign: 'center', color: '#94a3b8', fontSize: 14 }}>
        <div style={{ fontSize: 28, marginBottom: 12 }}>👤</div>
        No personas generated yet.
      </div>
    )
  }

  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))',
      gap: 12,
    }}>
      {allPersonas.map((p, i) => (
        <div key={i} style={{
          padding: 14, borderRadius: 8, border: '1px solid #e2e8f0',
          background: '#fff',
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
            <span style={{ fontWeight: 600, fontSize: 14 }}>{p.name}</span>
            <span style={{ fontSize: 11, color: '#94a3b8' }}>
              {PLATFORM_LABELS[p.platform] || p.platform}
            </span>
          </div>
          <p style={{ margin: '0 0 6px', fontSize: 12, color: '#64748b' }}>{p.role}</p>
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
            <span style={{
              fontSize: 10, padding: '2px 7px', borderRadius: 10,
              background: BIAS_COLORS[p.bias] || '#e2e8f0', color: '#fff',
            }}>{p.bias}</span>
            <span style={{
              fontSize: 10, padding: '2px 7px', borderRadius: 10,
              background: '#f1f5f9', color: '#64748b',
            }}>{p.mbti}</span>
          </div>
        </div>
      ))}
    </div>
  )
}
