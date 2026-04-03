import { useMemo, useState } from 'react'
import type { Platform, SocialPost, Persona } from '../types'
import { t } from '../tokens'
import { PLATFORM_OPTIONS } from '../constants'
import { PLATFORM_COLORS } from '../constants'

const PLATFORM_LABELS = Object.fromEntries(
  PLATFORM_OPTIONS.map(({ id, label }) => [id, label])
) as Record<Platform, string>

interface Props {
  posts: Partial<Record<Platform, SocialPost[]>>
  limit?: number
  personasMap?: Record<string, Persona>
}

const SENIORITY_BADGE: Record<string, { label: string; bg: string; color: string } | null> = {
  c_suite:   { label: 'C-Suite',   bg: '#fef2f2', color: '#dc2626' },
  vp:        { label: 'VP',        bg: '#fef2f2', color: '#dc2626' },
  director:  { label: 'Director',  bg: '#fef2f2', color: '#dc2626' },
  senior:    { label: 'Senior',    bg: '#eff6ff', color: '#2563eb' },
  lead:      { label: 'Lead',      bg: '#eff6ff', color: '#2563eb' },
  principal: { label: 'Principal', bg: '#eff6ff', color: '#2563eb' },
}

export function TopPosts({ posts, limit = 5, personasMap }: Props) {
  const [selectedPlatform, setSelectedPlatform] = useState<'all' | Platform>('all')

  const availablePlatforms = useMemo(() => {
    return (Object.keys(posts) as Platform[]).filter(p => (posts[p]?.length ?? 0) > 0)
  }, [posts])

  const filteredPosts = useMemo(() => {
    if (selectedPlatform === 'all') return posts
    const platformPosts = posts[selectedPlatform]
    if (!platformPosts) return {}
    return { [selectedPlatform]: platformPosts } as Partial<Record<Platform, SocialPost[]>>
  }, [posts, selectedPlatform])

  const top = useMemo(() => {
    const all: SocialPost[] = Object.values(filteredPosts).flatMap(list => list ?? [])
    if (all.length === 0) return []

    const getScore = (post: SocialPost) =>
      (post.weighted_score ?? 0) * 2 +
      (post.reply_count ?? 0) * 3 +
      (post.upvotes ?? 0) * 1

    const sorted = [...all].sort((a, b) => getScore(b) - getScore(a))
    let topPosts = sorted.slice(0, limit)

    // sentiment 다양성 보장: negative/constructive가 없으면 최고 점수 1개 추가
    const hasNeg = topPosts.some(p => p.sentiment === 'negative' || p.sentiment === 'constructive')
    if (!hasNeg) {
      const bestNeg = sorted.find(p => p.sentiment === 'negative' || p.sentiment === 'constructive')
      if (bestNeg) {
        topPosts = [...topPosts.slice(0, limit - 1), bestNeg]
      }
    }

    return topPosts
  }, [filteredPosts, limit])

  if (top.length === 0 && availablePlatforms.length === 0) return null

  return (
    <div style={{ background: t.color.bgPage, border: `1px solid ${t.color.border}`, borderRadius: t.radius.lg, padding: t.space[4], boxShadow: '0 1px 3px rgba(0,0,0,0.04)' }}>
      <p style={{ fontSize: t.font.size.sm, fontWeight: t.font.weight.semibold, color: t.color.textMuted, textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: t.space[2] }}>
        Notable Opinions
      </p>

      {/* Platform filter chips */}
      {availablePlatforms.length > 1 && (
        <div style={{ display: 'flex', gap: t.space[1], flexWrap: 'wrap', marginBottom: t.space[3] }}>
          <button
            onClick={() => setSelectedPlatform('all')}
            style={{
              padding: '4px 12px', fontSize: t.font.size.xs, fontWeight: t.font.weight.semibold,
              borderRadius: t.radius.pill, border: '1px solid',
              borderColor: selectedPlatform === 'all' ? t.color.primary : t.color.border,
              background: selectedPlatform === 'all' ? t.color.primary : t.color.bgPage,
              color: selectedPlatform === 'all' ? t.color.textInverse : t.color.textSecondary,
              cursor: 'pointer', transition: 'all 0.15s',
            }}
          >
            All
          </button>
          {availablePlatforms.map(platform => {
            const isActive = selectedPlatform === platform
            const platformColor = PLATFORM_COLORS[platform] || t.color.textMuted
            return (
              <button
                key={platform}
                onClick={() => setSelectedPlatform(platform)}
                style={{
                  display: 'flex', alignItems: 'center', gap: 5,
                  padding: '4px 12px', fontSize: t.font.size.xs, fontWeight: t.font.weight.semibold,
                  borderRadius: t.radius.pill, border: '1px solid',
                  borderColor: isActive ? platformColor : t.color.border,
                  background: isActive ? platformColor : t.color.bgPage,
                  color: isActive ? t.color.textInverse : t.color.textSecondary,
                  cursor: 'pointer', transition: 'all 0.15s',
                }}
              >
                <span style={{
                  width: 6, height: 6, borderRadius: '50%',
                  background: isActive ? t.color.textInverse : platformColor,
                  display: 'inline-block', flexShrink: 0,
                }} />
                {PLATFORM_LABELS[platform] ?? platform}
              </button>
            )
          })}
        </div>
      )}

      {top.length === 0 && (
        <p style={{ fontSize: t.font.size.md, color: t.color.textMuted, margin: `${t.space[3]} 0 0` }}>
          No posts found for this platform.
        </p>
      )}

      {top.map((post, i) => {
        const dotColor = post.sentiment === 'positive' ? '#4ade80'
          : post.sentiment === 'negative' ? '#f87171'
          : post.sentiment === 'neutral' ? '#d1d5db'
          : post.sentiment === 'constructive' ? '#3b82f6'
          : undefined

        const persona = personasMap?.[post.author_node_id]
        const badge = persona?.seniority ? SENIORITY_BADGE[persona.seniority] ?? null : null

        return (
        <div key={post.id} style={{
          display: 'flex', alignItems: 'flex-start', gap: t.space[3],
          padding: `${t.space[3]} 0`,
          borderBottom: i < top.length - 1 ? `1px solid ${t.color.bgSubtle}` : 'none',
        }}>
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: t.space[1], flexShrink: 0 }}>
            {dotColor && (
              <span style={{ width: 8, height: 8, borderRadius: '50%', background: dotColor, display: 'inline-block' }} />
            )}
            <span style={{ fontSize: 18, fontWeight: 800, color: t.color.border, width: 28, textAlign: 'center', lineHeight: 1 }}>
              {i + 1}
            </span>
          </div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <p style={{ fontSize: t.font.size.md, color: t.color.textPrimary, lineHeight: 1.5, margin: `0 0 ${t.space[1]}` }}>
              "{post.content}"
            </p>
            <p style={{ fontSize: t.font.size.xs, color: t.color.textMuted, margin: 0, display: 'flex', alignItems: 'center', gap: t.space[1], flexWrap: 'wrap' }}>
              <span>{post.author_name}</span>
              {badge && (
                <span style={{
                  fontSize: t.font.size.xs, fontWeight: t.font.weight.bold, padding: '1px 6px',
                  borderRadius: t.radius.md, background: badge.bg, color: badge.color,
                  letterSpacing: '0.02em',
                }}>
                  {badge.label}
                </span>
              )}
              <span>· {PLATFORM_LABELS[post.platform]} · Round {post.round_num}</span>
              {(post.reply_count ?? 0) > 0 && (
                <span style={{ color: t.color.primary, fontWeight: t.font.weight.semibold }}>
                  · {post.reply_count} {post.reply_count === 1 ? 'reply' : 'replies'}
                </span>
              )}
            </p>
          </div>
          {post.upvotes > 0 && (
            <div style={{ display: 'flex', alignItems: 'center', gap: t.space[1], fontSize: t.font.size.sm, fontWeight: t.font.weight.semibold, color: t.color.success, flexShrink: 0 }}>
              ▲ {post.upvotes}
            </div>
          )}
        </div>
        )
      })}
    </div>
  )
}
