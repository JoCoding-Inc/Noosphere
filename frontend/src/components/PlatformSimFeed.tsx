import { useState, useMemo, useCallback } from 'react'
import type { Platform, SocialPost } from '../types'
import { HackerNewsUI } from './platforms/HackerNewsUI'
import { ProductHuntUI } from './platforms/ProductHuntUI'
import { RedditUI } from './platforms/RedditUI'
import { LinkedInUI } from './platforms/LinkedInUI'
import { IndieHackersUI } from './platforms/IndieHackersUI'
import { t } from '../tokens'

interface Props {
  postsByPlatform: Partial<Record<Platform, SocialPost[]>>
  ideaText?: string
  forcedTab?: Platform
}

const COLLAPSE_THRESHOLD = 3

const PLATFORM_META: Record<Platform, { label: string; icon: string; color: string }> = {
  hackernews:      { label: 'Hacker News',      icon: '🟠', color: '#ff6600' },
  producthunt:     { label: 'Product Hunt',      icon: '🔴', color: '#da552f' },
  indiehackers:    { label: 'Indie Hackers',     icon: '🟣', color: '#0cce6b' },
  reddit_startups: { label: 'r/startups',        icon: '🟤', color: '#ff4500' },
  linkedin:        { label: 'LinkedIn',           icon: '🔵', color: '#0a66c2' },
}

/**
 * Filters posts so that collapsed threads only show the first COLLAPSE_THRESHOLD replies.
 * expandedThreads is a Set of parent post IDs whose replies are fully expanded.
 */
function filterPostsByThreadState(posts: SocialPost[], expandedThreads: Set<string>): SocialPost[] {
  // Group replies by parent_id
  const repliesByParent = new Map<string, SocialPost[]>()
  for (const p of posts) {
    if (p.parent_id) {
      const arr = repliesByParent.get(p.parent_id)
      if (arr) arr.push(p)
      else repliesByParent.set(p.parent_id, [p])
    }
  }

  // Build set of post IDs to exclude (collapsed replies beyond threshold)
  const excludeIds = new Set<string>()
  for (const [parentId, replies] of repliesByParent) {
    if (replies.length > COLLAPSE_THRESHOLD && !expandedThreads.has(parentId)) {
      for (let i = COLLAPSE_THRESHOLD; i < replies.length; i++) {
        excludeIds.add(replies[i].id)
      }
    }
  }

  return posts.filter(p => !excludeIds.has(p.id))
}

/** Returns info about collapsible threads for a given post list */
function getCollapsibleThreads(posts: SocialPost[]): Map<string, number> {
  const replyCounts = new Map<string, number>()
  for (const p of posts) {
    if (p.parent_id) {
      replyCounts.set(p.parent_id, (replyCounts.get(p.parent_id) ?? 0) + 1)
    }
  }
  // Only return threads that exceed the threshold
  const result = new Map<string, number>()
  for (const [parentId, count] of replyCounts) {
    if (count > COLLAPSE_THRESHOLD) result.set(parentId, count)
  }
  return result
}

export function PlatformSimFeed({ postsByPlatform, ideaText = '', forcedTab }: Props) {
  const activePlatforms = Object.keys(postsByPlatform).filter(
    k => (postsByPlatform[k as Platform]?.length ?? 0) > 0
  ) as Platform[]

  const [activeTab, setActiveTab] = useState<Platform | null>(null)
  const [expandedThreads, setExpandedThreads] = useState<Set<string>>(new Set())

  const toggleThread = useCallback((parentId: string) => {
    setExpandedThreads(prev => {
      const next = new Set(prev)
      if (next.has(parentId)) next.delete(parentId)
      else next.add(parentId)
      return next
    })
  }, [])

  // If activeTab is no longer in the visible platforms (e.g. round filter changed),
  // fall back to the first available platform so content isn't blank
  const tab = forcedTab ?? (activeTab && activePlatforms.includes(activeTab) ? activeTab : null) ?? activePlatforms[0] ?? null
  const rawPosts = tab ? (postsByPlatform[tab] ?? []) : []

  const collapsibleThreads = useMemo(() => getCollapsibleThreads(rawPosts), [rawPosts])
  const posts = useMemo(
    () => filterPostsByThreadState(rawPosts, expandedThreads),
    [rawPosts, expandedThreads]
  )

  if (activePlatforms.length === 0) {
    return (
      <div style={{ padding: 48, textAlign: 'center', color: t.color.textMuted, fontSize: t.font.size.lg }}>
        <div style={{ fontSize: 28, marginBottom: t.space[3] }}>💬</div>
        No posts available.
      </div>
    )
  }

  return (
    <div>
      {/* 플랫폼 탭 */}
      <div style={{ display: 'flex', gap: t.space[1], marginBottom: t.space[4], flexWrap: 'wrap' }}>
        {activePlatforms.map(platform => {
          const meta = PLATFORM_META[platform]
          const isActive = tab === platform
          const count = postsByPlatform[platform]?.length ?? 0
          return (
            <button
              key={platform}
              onClick={() => setActiveTab(platform)}
              style={{
                display: 'flex', alignItems: 'center', gap: t.space[2],
                padding: '6px 14px', fontSize: t.font.size.md, borderRadius: t.radius.pill,
                border: `1.5px solid ${isActive ? meta.color : t.color.border}`,
                background: isActive ? meta.color : t.color.bgPage,
                color: isActive ? t.color.textInverse : t.color.textStrong,
                cursor: 'pointer', fontWeight: isActive ? t.font.weight.semibold : t.font.weight.normal,
                transition: 'all 0.15s',
                boxShadow: isActive ? `0 2px 8px ${meta.color}40` : 'none',
              }}
            >
              <span>{meta.icon}</span>
              {meta.label}
              <span style={{
                fontSize: t.font.size.xs, padding: '0px 5px', borderRadius: t.radius.md,
                background: isActive ? 'rgba(255,255,255,0.25)' : t.color.bgSubtle,
                color: isActive ? t.color.textInverse : t.color.textMuted,
              }}>
                {count}
              </span>
            </button>
          )
        })}
      </div>

      {/* 플랫폼별 UI */}
      {tab && (
        <div key={tab} className="tab-content">
          {tab === 'hackernews'      && <HackerNewsUI posts={posts} collapsibleThreads={collapsibleThreads} expandedThreads={expandedThreads} onToggleThread={toggleThread} />}
          {tab === 'producthunt'     && <ProductHuntUI posts={posts} idea={ideaText} collapsibleThreads={collapsibleThreads} expandedThreads={expandedThreads} onToggleThread={toggleThread} />}
          {tab === 'reddit_startups' && <RedditUI posts={posts} collapsibleThreads={collapsibleThreads} expandedThreads={expandedThreads} onToggleThread={toggleThread} />}
          {tab === 'linkedin'        && <LinkedInUI posts={posts} collapsibleThreads={collapsibleThreads} expandedThreads={expandedThreads} onToggleThread={toggleThread} />}
          {tab === 'indiehackers'    && <IndieHackersUI posts={posts} collapsibleThreads={collapsibleThreads} expandedThreads={expandedThreads} onToggleThread={toggleThread} />}
        </div>
      )}
    </div>
  )
}
