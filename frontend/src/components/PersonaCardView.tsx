import { useMemo } from 'react'
import type { Persona, Platform, SocialPost } from '../types'
import { t } from '../tokens'

const PLATFORM_LABELS: Record<Platform, string> = {
  hackernews: 'HN',
  producthunt: 'PH',
  indiehackers: 'IH',
  reddit_startups: 'Reddit',
  linkedin: 'LinkedIn',
}

const PLATFORM_COLORS: Record<Platform, string> = {
  hackernews:      '#ff6600',
  producthunt:     '#da552f',
  indiehackers:    '#4f46e5',
  reddit_startups: '#ff4500',
  linkedin:        '#0077b5',
}

const BIAS_COLORS: Record<string, string> = {
  academic:   '#6366f1',
  commercial: '#22c55e',
  skeptic:    '#f59e0b',
  evangelist: '#ec4899',
}

const SENIORITY_LABELS: Record<string, string> = {
  intern: 'Intern',
  junior: 'Junior',
  mid: 'Mid',
  senior: 'Senior',
  lead: 'Lead',
  principal: 'Principal',
  director: 'Director',
  vp: 'VP',
  c_suite: 'C-Suite',
}

function MiniBar({ value, max = 10, color }: { value: number; max?: number; color: string }) {
  const pct = Math.round((value / max) * 100)
  return (
    <div style={{ flex: 1, height: 4, borderRadius: 2, background: t.color.border }}>
      <div style={{ width: `${pct}%`, height: '100%', borderRadius: 2, background: color }} />
    </div>
  )
}

type PersonaWithPlatform = Persona & { platform: Platform }

interface PersonaCardViewProps {
  personas: Partial<Record<Platform, Persona[]>> | null | undefined
  allPosts?: SocialPost[]
}

export function PersonaCardView({ personas, allPosts }: PersonaCardViewProps) {
  const allPersonas: PersonaWithPlatform[] = Object.entries(personas ?? {}).flatMap(([platform, list]) =>
    (list ?? []).map(p => ({ ...p, platform: platform as Platform }))
  )

  // Compute influence scores: upvotes + (replies received * 2)
  const influenceScores = useMemo(() => {
    if (!allPosts || allPosts.length === 0) return new Map<string, number>()
    const scores = new Map<string, number>()
    // Index posts by id for parent lookup
    const postIdSet = new Map<string, string>() // post.id -> author_node_id
    for (const post of allPosts) {
      postIdSet.set(post.id, post.author_node_id)
    }
    // Aggregate upvotes per author
    for (const post of allPosts) {
      const prev = scores.get(post.author_node_id) ?? 0
      scores.set(post.author_node_id, prev + (post.upvotes ?? 0))
    }
    // Count replies received (parent_id -> parent author gets +2)
    for (const post of allPosts) {
      if (post.parent_id) {
        const parentAuthor = postIdSet.get(post.parent_id)
        if (parentAuthor) {
          const prev = scores.get(parentAuthor) ?? 0
          scores.set(parentAuthor, prev + 2)
        }
      }
    }
    return scores
  }, [allPosts])

  if (allPersonas.length === 0) {
    return (
      <div style={{ padding: 48, textAlign: 'center', color: t.color.textMuted, fontSize: t.font.size.lg }}>
        <div style={{ fontSize: 28, marginBottom: t.space[3] }}>👤</div>
        No personas generated yet.
      </div>
    )
  }

  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))',
      gap: t.space[3],
    }}>
      {allPersonas.map((p, i) => {
        const platformColor = PLATFORM_COLORS[p.platform] || t.color.textMuted
        const biasColor = (p.bias ? BIAS_COLORS[p.bias] : undefined) || t.color.textMuted
        const biasBg = biasColor + '15'
        const biasBorder = '1px solid ' + biasColor + '30'
        return (
          <div key={i} style={{
            borderRadius: t.radius.md,
            border: `1px solid ${t.color.border}`,
            background: t.color.bgPage,
            overflow: 'hidden',
          }}>
            {/* Platform accent bar */}
            <div style={{ height: 3, background: platformColor }} />

            <div style={{ padding: t.space[4] }}>
              {/* Avatar + Name/MBTI */}
              <div style={{ display: 'flex', alignItems: 'center', gap: t.space[2], marginBottom: t.space[2] }}>
                <div style={{
                  width: 32, height: 32, borderRadius: '50%',
                  background: platformColor + '18',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: t.font.size.lg, fontWeight: t.font.weight.bold, color: platformColor, flexShrink: 0,
                }}>
                  {(p.name?.[0] ?? '?').toUpperCase()}
                </div>
                <div style={{ minWidth: 0, flex: 1 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
                    <span style={{ fontWeight: t.font.weight.semibold, fontSize: t.font.size.md, color: t.color.textPrimary }}>{p.name}</span>
                    <span style={{
                      fontSize: 10, fontWeight: t.font.weight.semibold, flexShrink: 0, marginLeft: t.space[1],
                      color: platformColor,
                    }}>
                      {PLATFORM_LABELS[p.platform] || p.platform}
                    </span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: t.space[1] }}>
                    <span style={{ fontSize: t.font.size.xs, color: t.color.textMuted }}>{p.mbti}</span>
                    {p.region && (
                      <span style={{
                        background: t.color.border, borderRadius: 4,
                        padding: '2px 6px', fontSize: t.font.size.xs, color: t.color.textStrong,
                        fontWeight: t.font.weight.semibold,
                      }}>{p.region}</span>
                    )}
                  </div>
                </div>
              </div>

              {/* Role + seniority/company */}
              <p style={{ margin: `0 0 ${t.space[1]}`, fontSize: t.font.size.sm, color: t.color.textStrong }}>{p.role}</p>
              {(p.seniority || p.company || p.age) && (
                <div style={{ display: 'flex', alignItems: 'center', gap: t.space[2], margin: `0 0 ${t.space[2]}` }}>
                  <span style={{ fontSize: 10, color: t.color.textMuted }}>
                    {[
                      p.seniority ? SENIORITY_LABELS[p.seniority] || p.seniority : null,
                      p.company || null,
                      p.age ? `${p.age}y` : null,
                    ].filter(Boolean).join(' · ')}
                  </span>
                  {p.generation && (
                    <span style={{
                      display: 'inline-block',
                      fontSize: 9, fontWeight: t.font.weight.bold, padding: '1px 6px', borderRadius: t.radius.md,
                      background: t.color.primaryLight, color: t.color.primaryHover, border: '1px solid #c7d2fe',
                      whiteSpace: 'nowrap',
                    }}>{p.generation}</span>
                  )}
                </div>
              )}

              {/* Bias tag (legacy) or affiliation tag */}
              {p.bias ? (
                <span style={{
                  display: 'inline-block',
                  fontSize: 10, fontWeight: t.font.weight.bold, padding: '2px 7px', borderRadius: t.radius.lg,
                  background: biasBg, color: biasColor, border: biasBorder,
                  textTransform: 'capitalize',
                }}>{p.bias}</span>
              ) : p.affiliation ? (
                <span style={{
                  display: 'inline-block',
                  fontSize: 10, fontWeight: t.font.weight.bold, padding: '2px 7px', borderRadius: t.radius.lg,
                  background: '#6366f115', color: '#6366f1', border: '1px solid #6366f130',
                  textTransform: 'capitalize',
                }}>{p.affiliation.replace('_', ' ')}</span>
              ) : null}

              {/* Dimension bars: skepticism, commercial_focus, innovation_openness */}
              {(p.skepticism != null || p.commercial_focus != null || p.innovation_openness != null) && (
                <div style={{ marginTop: t.space[2], display: 'flex', flexDirection: 'column', gap: t.space[1] }}>
                  {p.skepticism != null && (
                    <div style={{ display: 'flex', alignItems: 'center', gap: t.space[2] }}>
                      <span style={{ fontSize: 9, color: t.color.textMuted, width: 52, flexShrink: 0 }}>Skepticism</span>
                      <MiniBar value={p.skepticism} color={t.color.warning} />
                      <span style={{ fontSize: 9, color: t.color.textSecondary, width: 14, textAlign: 'right' }}>{p.skepticism}</span>
                    </div>
                  )}
                  {p.commercial_focus != null && (
                    <div style={{ display: 'flex', alignItems: 'center', gap: t.space[2] }}>
                      <span style={{ fontSize: 9, color: t.color.textMuted, width: 52, flexShrink: 0 }}>Commercial</span>
                      <MiniBar value={p.commercial_focus} color={t.color.success} />
                      <span style={{ fontSize: 9, color: t.color.textSecondary, width: 14, textAlign: 'right' }}>{p.commercial_focus}</span>
                    </div>
                  )}
                  {p.innovation_openness != null && (
                    <div style={{ display: 'flex', alignItems: 'center', gap: t.space[2] }}>
                      <span style={{ fontSize: 9, color: t.color.textMuted, width: 52, flexShrink: 0 }}>Innovation</span>
                      <MiniBar value={p.innovation_openness} color={t.color.primary} />
                      <span style={{ fontSize: 9, color: t.color.textSecondary, width: 14, textAlign: 'right' }}>{p.innovation_openness}</span>
                    </div>
                  )}
                </div>
              )}

              {/* Interests */}
              {p.interests.slice(0, 3).map((interest, j) => (
                <span key={j} style={{
                  display: 'inline-block', fontSize: 10, color: t.color.textSecondary,
                  background: t.color.bgSubtle, borderRadius: 4, padding: '1px 5px',
                  margin: `${t.space[1]} 2px 0`,
                }}>{interest}</span>
              ))}

              {/* JTBD */}
              {p.jtbd && (
                <p style={{ margin: `6px 0 0`, fontSize: 10, color: t.color.textSecondary, lineHeight: 1.4, fontStyle: 'italic' }}>
                  JTBD: {p.jtbd}
                </p>
              )}

              {/* Cognitive pattern */}
              {p.cognitive_pattern && (
                <span style={{
                  display: 'inline-block', fontSize: 9, color: t.color.textStrong,
                  background: t.color.border, borderRadius: 4, padding: '2px 6px',
                  marginTop: t.space[2],
                }}>{p.cognitive_pattern.length > 50 ? p.cognitive_pattern.slice(0, 47) + '...' : p.cognitive_pattern}</span>
              )}

              {/* Emotional state */}
              {p.emotional_state && (
                <span style={{
                  display: 'inline-block', fontSize: 9, color: '#ec4899',
                  background: '#ec489910', borderRadius: 4, padding: '2px 5px',
                  marginTop: t.space[1],
                }}>{p.emotional_state}</span>
              )}

              {/* Influence score */}
              {(() => {
                const score = influenceScores.get(p.node_id) ?? 0
                if (score <= 0) return null
                return (
                  <div style={{
                    marginTop: t.space[2], display: 'inline-block',
                    fontSize: 10, fontWeight: t.font.weight.bold, padding: '2px 8px',
                    borderRadius: t.radius.lg, background: '#fef3c7', color: '#b45309',
                    border: `1px solid ${t.color.warningBorder}`,
                  }}>
                    Influence: {score}
                  </div>
                )
              })()}

              {/* Attitude shift indicator */}
              {(() => {
                const shift = p.attitude_shift
                if (shift == null || Math.abs(shift) < 0.1) return null
                const isPositive = shift > 0
                const arrow = isPositive ? '▲' : '▼'
                const color = isPositive ? t.color.success : t.color.danger
                const displayVal = isPositive ? `+${shift.toFixed(1)}` : shift.toFixed(1)
                const tooltip = p.attitude_history && p.attitude_history.length > 0
                  ? p.attitude_history.map(h => `Round ${h.round}: ${h.delta >= 0 ? '+' : ''}${h.delta.toFixed(1)}`).join('\n')
                  : undefined
                return (
                  <div
                    style={{
                      marginTop: t.space[2], fontSize: 10, fontWeight: t.font.weight.semibold,
                      color, display: 'inline-flex', alignItems: 'center', gap: t.space[1],
                    }}
                    title={tooltip}
                  >
                    <span>{arrow}</span>
                    <span>Attitude {displayVal}</span>
                  </div>
                )
              })()}
            </div>
          </div>
        )
      })}
    </div>
  )
}
