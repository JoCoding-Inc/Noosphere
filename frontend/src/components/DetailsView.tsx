import { useState, useEffect, useMemo } from 'react'
import type { Platform, SocialPost, Persona, ReportJSON } from '../types'
import { PlatformSimFeed } from './PlatformSimFeed'
import { PersonaCardView } from './PersonaCardView'

type DetailTab = 'feed' | 'personas' | 'network'

interface Props {
  posts: Partial<Record<Platform, SocialPost[]>>
  personas: Partial<Record<Platform, Persona[]>>
  forcedTab?: DetailTab
  allPosts?: SocialPost[]
  reportJson?: ReportJSON
}

const RISK_COLOR: Record<string, string> = {
  low: '#22c55e',
  medium: '#f59e0b',
  high: '#ef4444',
}

function NetworkTab({ reportJson }: { reportJson?: ReportJSON }) {
  const interactions = useMemo(() => {
    const list = reportJson?.interaction_network ?? []
    return [...list]
      .sort((a, b) => b.count - a.count)
      .slice(0, 20)
  }, [reportJson])

  const echoRisk = reportJson?.echo_chamber_risk

  if (interactions.length === 0 && !echoRisk) {
    return <p style={{ color: '#94a3b8', fontSize: 13 }}>No network data available.</p>
  }

  return (
    <div>
      {/* Echo Chamber Risk */}
      {echoRisk && Object.keys(echoRisk).length > 0 && (
        <div style={{ marginBottom: 24 }}>
          <h3 style={{ fontSize: 14, fontWeight: 700, color: '#1e293b', marginBottom: 12 }}>Echo Chamber Risk</h3>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10 }}>
            {Object.entries(echoRisk).map(([platform, data]) => (
              <div key={platform} style={{
                padding: '10px 14px', borderRadius: 8,
                border: `1px solid ${RISK_COLOR[data.risk] ?? '#e2e8f0'}30`,
                background: `${RISK_COLOR[data.risk] ?? '#f1f5f9'}10`,
                minWidth: 140,
              }}>
                <div style={{ fontSize: 12, fontWeight: 600, color: '#1e293b', marginBottom: 4 }}>
                  {platform}
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <span style={{
                    fontSize: 11, padding: '1px 7px', borderRadius: 8,
                    background: `${RISK_COLOR[data.risk] ?? '#94a3b8'}20`,
                    color: RISK_COLOR[data.risk] ?? '#94a3b8',
                    fontWeight: 600, textTransform: 'capitalize',
                  }}>
                    {data.risk}
                  </span>
                  <span style={{ fontSize: 11, color: '#64748b' }}>
                    entropy: {(data.entropy ?? 0).toFixed(2)}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Interaction Network */}
      {interactions.length > 0 && (
        <div>
          <h3 style={{ fontSize: 14, fontWeight: 700, color: '#1e293b', marginBottom: 12 }}>
            Interaction Network (Top {interactions.length})
          </h3>
          <div style={{
            border: '1px solid #e2e8f0', borderRadius: 8, overflow: 'hidden',
          }}>
            {/* Header */}
            <div style={{
              display: 'grid', gridTemplateColumns: '1fr 1fr 80px 80px 1fr',
              padding: '8px 14px', background: '#f8fafc',
              fontSize: 11, fontWeight: 600, color: '#64748b',
              borderBottom: '1px solid #e2e8f0',
            }}>
              <span>From</span>
              <span>To</span>
              <span style={{ textAlign: 'center' }}>Agree</span>
              <span style={{ textAlign: 'center' }}>Disagree</span>
              <span>Ratio</span>
            </div>
            {/* Rows */}
            {interactions.map((edge, i) => {
              const agree = edge.agree_count ?? 0
              const disagree = edge.disagree_count ?? 0
              const total = agree + disagree
              const agreePct = total > 0 ? Math.round((agree / total) * 100) : 0
              const disagreePct = total > 0 ? 100 - agreePct : 0

              return (
                <div key={i} style={{
                  display: 'grid', gridTemplateColumns: '1fr 1fr 80px 80px 1fr',
                  padding: '7px 14px', fontSize: 12, color: '#1e293b',
                  borderBottom: i < interactions.length - 1 ? '1px solid #f1f5f9' : 'none',
                  background: i % 2 === 0 ? '#fff' : '#fafafa',
                }}>
                  <span style={{ fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {edge.from_name ?? edge.from}
                  </span>
                  <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {edge.to_name ?? edge.to}
                  </span>
                  <span style={{ textAlign: 'center', color: '#22c55e', fontWeight: 500 }}>{agree}</span>
                  <span style={{ textAlign: 'center', color: '#ef4444', fontWeight: 500 }}>{disagree}</span>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <div style={{
                      flex: 1, height: 6, borderRadius: 3, overflow: 'hidden',
                      background: '#f1f5f9', display: 'flex',
                    }}>
                      {agreePct > 0 && <div style={{ width: `${agreePct}%`, background: '#22c55e' }} />}
                      {disagreePct > 0 && <div style={{ width: `${disagreePct}%`, background: '#ef4444' }} />}
                    </div>
                    <span style={{ fontSize: 10, color: '#94a3b8', whiteSpace: 'nowrap' }}>
                      {total > 0 ? `${agreePct}%` : '-'}
                    </span>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}

export function DetailsView({ posts, personas, forcedTab, allPosts, reportJson }: Props) {
  const [tab, setTab] = useState<DetailTab>('feed')
  const activeTab = forcedTab ?? tab

  // Sync internal tab state when forcedTab changes externally
  useEffect(() => {
    if (forcedTab) setTab(forcedTab)
  }, [forcedTab])

  const tabs: { id: DetailTab; label: string }[] = [
    { id: 'feed', label: 'Social Feed' },
    { id: 'personas', label: 'Personas' },
    { id: 'network', label: 'Network' },
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
        {activeTab === 'personas' && <PersonaCardView personas={personas} allPosts={allPosts} />}
        {activeTab === 'network' && <NetworkTab reportJson={reportJson} />}
      </div>
    </div>
  )
}
