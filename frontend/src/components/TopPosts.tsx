import { useMemo, useState } from 'react'
import type { Platform, SocialPost, Persona } from '../types'
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
    <div style={{ background: '#fff', border: '1px solid #e2e8f0', borderRadius: 10, padding: 16, boxShadow: '0 1px 3px rgba(0,0,0,0.04)' }}>
      <p style={{ fontSize: 12, fontWeight: 600, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 8 }}>
        Notable Opinions
      </p>

      {/* Platform filter chips */}
      {availablePlatforms.length > 1 && (
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 12 }}>
          <button
            onClick={() => setSelectedPlatform('all')}
            style={{
              padding: '4px 12px', fontSize: 11, fontWeight: 600,
              borderRadius: 20, border: '1px solid',
              borderColor: selectedPlatform === 'all' ? '#6366f1' : '#e2e8f0',
              background: selectedPlatform === 'all' ? '#6366f1' : '#fff',
              color: selectedPlatform === 'all' ? '#fff' : '#64748b',
              cursor: 'pointer', transition: 'all 0.15s',
            }}
          >
            All
          </button>
          {availablePlatforms.map(platform => {
            const isActive = selectedPlatform === platform
            const platformColor = PLATFORM_COLORS[platform] || '#94a3b8'
            return (
              <button
                key={platform}
                onClick={() => setSelectedPlatform(platform)}
                style={{
                  display: 'flex', alignItems: 'center', gap: 5,
                  padding: '4px 12px', fontSize: 11, fontWeight: 600,
                  borderRadius: 20, border: '1px solid',
                  borderColor: isActive ? platformColor : '#e2e8f0',
                  background: isActive ? platformColor : '#fff',
                  color: isActive ? '#fff' : '#64748b',
                  cursor: 'pointer', transition: 'all 0.15s',
                }}
              >
                <span style={{
                  width: 6, height: 6, borderRadius: '50%',
                  background: isActive ? '#fff' : platformColor,
                  display: 'inline-block', flexShrink: 0,
                }} />
                {PLATFORM_LABELS[platform] ?? platform}
              </button>
            )
          })}
        </div>
      )}

      {top.length === 0 && (
        <p style={{ fontSize: 13, color: '#94a3b8', margin: '12px 0 0' }}>
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
          display: 'flex', alignItems: 'flex-start', gap: 12,
          padding: '12px 0',
          borderBottom: i < top.length - 1 ? '1px solid #f1f5f9' : 'none',
        }}>
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4, flexShrink: 0 }}>
            {dotColor && (
              <span style={{ width: 8, height: 8, borderRadius: '50%', background: dotColor, display: 'inline-block' }} />
            )}
            <span style={{ fontSize: 18, fontWeight: 800, color: '#e2e8f0', width: 28, textAlign: 'center', lineHeight: 1 }}>
              {i + 1}
            </span>
          </div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <p style={{ fontSize: 13, color: '#1e293b', lineHeight: 1.5, margin: '0 0 4px' }}>
              "{post.content}"
            </p>
            <p style={{ fontSize: 11, color: '#94a3b8', margin: 0, display: 'flex', alignItems: 'center', gap: 4, flexWrap: 'wrap' }}>
              <span>{post.author_name}</span>
              {badge && (
                <span style={{
                  fontSize: 9, fontWeight: 700, padding: '1px 6px',
                  borderRadius: 8, background: badge.bg, color: badge.color,
                  letterSpacing: '0.02em',
                }}>
                  {badge.label}
                </span>
              )}
              <span>· {PLATFORM_LABELS[post.platform]} · Round {post.round_num}</span>
              {(post.reply_count ?? 0) > 0 && (
                <span style={{ color: '#6366f1', fontWeight: 600 }}>
                  · {post.reply_count} {post.reply_count === 1 ? 'reply' : 'replies'}
                </span>
              )}
            </p>
          </div>
          {post.upvotes > 0 && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 12, fontWeight: 600, color: '#22c55e', flexShrink: 0 }}>
              ▲ {post.upvotes}
            </div>
          )}
        </div>
        )
      })}
    </div>
  )
}
