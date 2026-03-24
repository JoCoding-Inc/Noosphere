import { useState, useEffect } from 'react'
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

  // Sync internal tab state when forcedTab changes externally
  useEffect(() => {
    if (forcedTab && forcedTab !== tab) setTab(forcedTab)
  }, [forcedTab, tab])

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

      <div key={activeTab} className="tab-content">
        {activeTab === 'feed' && <PlatformSimFeed postsByPlatform={posts} />}
        {activeTab === 'personas' && <PersonaCardView personas={personas} />}
      </div>
    </div>
  )
}
