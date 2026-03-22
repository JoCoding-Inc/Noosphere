import { useState } from 'react'
import type { Platform, SocialPost, Persona } from '../types'
import { PlatformSimFeed } from './PlatformSimFeed'
import { PersonaCardView } from './PersonaCardView'

type DetailTab = 'feed' | 'personas'

interface Props {
  posts: Partial<Record<Platform, SocialPost[]>>
  personas: Partial<Record<Platform, Persona[]>>
  forcedTab?: DetailTab
}

export function DetailsView({ posts, personas, forcedTab }: Props) {
  const [tab, setTab] = useState<DetailTab>('feed')
  const activeTab = forcedTab ?? tab

  // Extract sorted unique round numbers from all posts
  const allPosts = Object.values(posts).flat() as SocialPost[]
  const rounds = [...new Set(allPosts.map(p => p.round_num))].sort((a, b) => a - b)
  const [activeRound, setActiveRound] = useState<number | null>(rounds[0] ?? null)

  // Filter posts to active round (null = show all)
  const filteredPosts: Partial<Record<Platform, SocialPost[]>> = activeRound === null
    ? posts
    : Object.fromEntries(
        Object.entries(posts).map(([platform, platformPosts]) => [
          platform,
          (platformPosts ?? []).filter(p => p.round_num === activeRound),
        ])
      ) as Partial<Record<Platform, SocialPost[]>>

  const tabs: { id: DetailTab; label: string }[] = [
    { id: 'feed', label: 'Social Feed' },
    { id: 'personas', label: 'Personas' },
  ]

  return (
    <div>
      {/* Sub-tab navigation */}
      <div style={{ display: 'flex', gap: 4, marginBottom: 20, borderBottom: '1px solid #e2e8f0' }}>
        {tabs.map(t => (
          <button key={t.id} onClick={() => setTab(t.id)}
            style={{
              padding: '8px 16px', fontSize: 13, cursor: 'pointer', border: 'none',
              background: 'none', fontWeight: activeTab === t.id ? 600 : 400,
              borderBottom: activeTab === t.id ? '2px solid #475569' : '2px solid transparent',
              color: activeTab === t.id ? '#1e293b' : '#94a3b8',
              transition: 'color 0.15s, border-color 0.15s',
            }}>
            {t.label}
          </button>
        ))}
      </div>

      {/* Round pagination — only shown on Social Feed tab when multiple rounds exist */}
      {activeTab === 'feed' && rounds.length > 1 && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
          <span style={{ fontSize: 12, color: '#94a3b8', fontWeight: 600 }}>Round</span>
          {rounds.map(r => (
            <button key={r} onClick={() => setActiveRound(r)}
              style={{
                width: 32, height: 32, borderRadius: '50%', border: 'none',
                background: activeRound === r ? '#1e293b' : '#f1f5f9',
                color: activeRound === r ? '#fff' : '#64748b',
                fontWeight: activeRound === r ? 700 : 400,
                fontSize: 13, cursor: 'pointer',
                transition: 'all 0.15s',
              }}>
              {r}
            </button>
          ))}
          <button onClick={() => setActiveRound(null)}
            style={{
              padding: '4px 10px', borderRadius: 6, border: '1px solid #e2e8f0',
              background: activeRound === null ? '#1e293b' : '#fff',
              color: activeRound === null ? '#fff' : '#64748b',
              fontSize: 12, cursor: 'pointer',
            }}>
            All
          </button>
        </div>
      )}

      <div key={activeTab} className="tab-content">
        {activeTab === 'feed' && <PlatformSimFeed postsByPlatform={filteredPosts} />}
        {activeTab === 'personas' && <PersonaCardView personas={personas} />}
      </div>
    </div>
  )
}
