import { useState } from 'react'
import type { Platform, SocialPost } from '../types'
import { HackerNewsUI } from './platforms/HackerNewsUI'
import { ProductHuntUI } from './platforms/ProductHuntUI'
import { RedditUI } from './platforms/RedditUI'
import { LinkedInUI } from './platforms/LinkedInUI'
import { IndieHackersUI } from './platforms/IndieHackersUI'

interface Props {
  postsByPlatform: Partial<Record<Platform, SocialPost[]>>
  ideaText?: string
}

const PLATFORM_META: Record<Platform, { label: string; icon: string; color: string }> = {
  hackernews:      { label: 'Hacker News',      icon: '🟠', color: '#ff6600' },
  producthunt:     { label: 'Product Hunt',      icon: '🔴', color: '#da552f' },
  indiehackers:    { label: 'Indie Hackers',     icon: '🟣', color: '#0cce6b' },
  reddit_startups: { label: 'r/startups',        icon: '🟤', color: '#ff4500' },
  linkedin:        { label: 'LinkedIn',           icon: '🔵', color: '#0a66c2' },
}

export function PlatformSimFeed({ postsByPlatform, ideaText = '' }: Props) {
  const activePlatforms = Object.keys(postsByPlatform).filter(
    k => (postsByPlatform[k as Platform]?.length ?? 0) > 0
  ) as Platform[]

  const [activeTab, setActiveTab] = useState<Platform | null>(null)

  const tab = activeTab ?? activePlatforms[0] ?? null
  const posts = tab ? (postsByPlatform[tab] ?? []) : []

  if (activePlatforms.length === 0) return null

  return (
    <div>
      {/* 플랫폼 탭 */}
      <div style={{ display: 'flex', gap: 4, marginBottom: 16, flexWrap: 'wrap' }}>
        {activePlatforms.map(platform => {
          const meta = PLATFORM_META[platform]
          const isActive = tab === platform
          const count = postsByPlatform[platform]?.length ?? 0
          return (
            <button
              key={platform}
              onClick={() => setActiveTab(platform)}
              style={{
                display: 'flex', alignItems: 'center', gap: 6,
                padding: '6px 14px', fontSize: 13, borderRadius: 20,
                border: `1.5px solid ${isActive ? meta.color : '#e2e8f0'}`,
                background: isActive ? meta.color : '#fff',
                color: isActive ? '#fff' : '#475569',
                cursor: 'pointer', fontWeight: isActive ? 600 : 400,
                transition: 'all 0.15s',
                boxShadow: isActive ? `0 2px 8px ${meta.color}40` : 'none',
              }}
            >
              <span>{meta.icon}</span>
              {meta.label}
              <span style={{
                fontSize: 11, padding: '0px 5px', borderRadius: 8,
                background: isActive ? 'rgba(255,255,255,0.25)' : '#f1f5f9',
                color: isActive ? '#fff' : '#94a3b8',
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
          {tab === 'hackernews'      && <HackerNewsUI posts={posts} />}
          {tab === 'producthunt'     && <ProductHuntUI posts={posts} idea={ideaText} />}
          {tab === 'reddit_startups' && <RedditUI posts={posts} />}
          {tab === 'linkedin'        && <LinkedInUI posts={posts} />}
          {tab === 'indiehackers'    && <IndieHackersUI posts={posts} />}
        </div>
      )}
    </div>
  )
}
