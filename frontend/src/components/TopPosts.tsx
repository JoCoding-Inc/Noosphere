import { useMemo } from 'react'
import type { Platform, SocialPost } from '../types'
import { PLATFORM_OPTIONS } from '../constants'

const PLATFORM_LABELS = Object.fromEntries(
  PLATFORM_OPTIONS.map(({ id, label }) => [id, label])
) as Record<Platform, string>

interface Props {
  posts: Partial<Record<Platform, SocialPost[]>>
  limit?: number
}

export function TopPosts({ posts, limit = 5 }: Props) {
  const top = useMemo(() => {
    const all: SocialPost[] = Object.values(posts).flatMap(list => list ?? [])
    return [...all].sort((a, b) => b.upvotes - a.upvotes).slice(0, limit)
  }, [posts, limit])

  if (top.length === 0) return null

  return (
    <div style={{ background: '#fff', border: '1px solid #e2e8f0', borderRadius: 10, padding: 16, boxShadow: '0 1px 3px rgba(0,0,0,0.04)' }}>
      <p style={{ fontSize: 12, fontWeight: 600, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 8 }}>
        상위 업보트 포스트
      </p>
      {top.map((post, i) => (
        <div key={post.id} style={{
          display: 'flex', alignItems: 'flex-start', gap: 12,
          padding: '12px 0',
          borderBottom: i < top.length - 1 ? '1px solid #f1f5f9' : 'none',
        }}>
          <span style={{ fontSize: 18, fontWeight: 800, color: '#e2e8f0', width: 28, flexShrink: 0, lineHeight: 1 }}>
            {i + 1}
          </span>
          <div style={{ flex: 1, minWidth: 0 }}>
            <p style={{ fontSize: 13, color: '#1e293b', lineHeight: 1.5, margin: '0 0 4px' }}>
              "{post.content}"
            </p>
            <p style={{ fontSize: 11, color: '#94a3b8', margin: 0 }}>
              {post.author_name} · {PLATFORM_LABELS[post.platform]} · Round {post.round_num}
            </p>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 12, fontWeight: 600, color: '#22c55e', flexShrink: 0 }}>
            ▲ {post.upvotes}
          </div>
        </div>
      ))}
    </div>
  )
}
