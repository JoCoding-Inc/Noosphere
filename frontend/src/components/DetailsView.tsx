import { useState, useEffect, useMemo } from 'react'
import type { Platform, SocialPost, Persona, ReportJSON } from '../types'
import { t } from '../tokens'
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
  low: t.color.success,
  medium: t.color.warning,
  high: t.color.danger,
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
    return <p style={{ color: t.color.textMuted, fontSize: t.font.size.md }}>No network data available.</p>
  }

  return (
    <div>
      {/* Echo Chamber Risk */}
      {echoRisk && Object.keys(echoRisk).length > 0 && (
        <div style={{ marginBottom: t.space[6] }}>
          <h3 style={{ fontSize: t.font.size.lg, fontWeight: t.font.weight.bold, color: t.color.textPrimary, marginBottom: t.space[1] }}>Echo Chamber Risk</h3>
          <p style={{ margin: '0 0 10px', fontSize: t.font.size.xs, color: t.color.textMuted }}>
            Entropy measures opinion diversity — higher entropy means more varied views exchanged; lower entropy suggests agents clustered around similar opinions (echo chamber).
          </p>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10 }}>
            {Object.entries(echoRisk).map(([platform, data]) => (
              <div key={platform} style={{
                padding: '10px 14px', borderRadius: t.radius.md,
                border: `1px solid ${RISK_COLOR[data.risk] ?? t.color.border}30`,
                background: `${RISK_COLOR[data.risk] ?? t.color.bgSubtle}10`,
                minWidth: 140,
              }}>
                <div style={{ fontSize: t.font.size.sm, fontWeight: t.font.weight.semibold, color: t.color.textPrimary, marginBottom: t.space[1] }}>
                  {platform}
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <span style={{
                    fontSize: t.font.size.xs, padding: '1px 7px', borderRadius: t.radius.md,
                    background: `${RISK_COLOR[data.risk] ?? t.color.textMuted}20`,
                    color: RISK_COLOR[data.risk] ?? t.color.textMuted,
                    fontWeight: t.font.weight.semibold, textTransform: 'capitalize',
                  }}>
                    {data.risk}
                  </span>
                  <span style={{ fontSize: t.font.size.xs, color: t.color.textSecondary }}>
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
          <h3 style={{ fontSize: t.font.size.lg, fontWeight: t.font.weight.bold, color: t.color.textPrimary, marginBottom: t.space[3] }}>
            Interaction Network (Top {interactions.length})
          </h3>
          <div style={{
            border: `1px solid ${t.color.border}`, borderRadius: t.radius.md, overflow: 'hidden',
          }}>
            {/* Header */}
            <div style={{
              display: 'grid', gridTemplateColumns: '1fr 1fr 80px 80px 1fr',
              padding: '8px 14px', background: t.color.bgCard,
              fontSize: t.font.size.xs, fontWeight: t.font.weight.semibold, color: t.color.textSecondary,
              borderBottom: `1px solid ${t.color.border}`,
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
                  padding: '7px 14px', fontSize: t.font.size.sm, color: t.color.textPrimary,
                  borderBottom: i < interactions.length - 1 ? `1px solid ${t.color.bgSubtle}` : 'none',
                  background: i % 2 === 0 ? t.color.bgPage : t.color.bgBody,
                }}>
                  <span style={{ fontWeight: t.font.weight.medium, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {edge.from_name ?? edge.from}
                  </span>
                  <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {edge.to_name ?? edge.to}
                  </span>
                  <span style={{ textAlign: 'center', color: t.color.success, fontWeight: t.font.weight.medium }}>{agree}</span>
                  <span style={{ textAlign: 'center', color: t.color.danger, fontWeight: t.font.weight.medium }}>{disagree}</span>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <div style={{
                      flex: 1, height: 6, borderRadius: 3, overflow: 'hidden',
                      background: t.color.bgSubtle, display: 'flex',
                    }}>
                      {agreePct > 0 && <div style={{ width: `${agreePct}%`, background: t.color.success }} />}
                      {disagreePct > 0 && <div style={{ width: `${disagreePct}%`, background: t.color.danger }} />}
                    </div>
                    <span style={{ fontSize: t.font.size.xs, color: t.color.textMuted, whiteSpace: 'nowrap' }}>
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
      <div style={{ display: 'flex', gap: t.space[1], marginBottom: t.space[5], borderBottom: `1px solid ${t.color.border}` }}>
        {tabs.map(tab => (
          <button key={tab.id} onClick={() => setTab(tab.id)}
            style={{
              padding: '8px 16px', fontSize: t.font.size.md, cursor: 'pointer', border: 'none',
              background: 'none', fontWeight: activeTab === tab.id ? t.font.weight.semibold : t.font.weight.normal,
              borderBottom: activeTab === tab.id ? `2px solid ${t.color.textStrong}` : '2px solid transparent',
              color: activeTab === tab.id ? t.color.textPrimary : t.color.textMuted,
              transition: 'color 0.15s, border-color 0.15s',
            }}>
            {tab.label}
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
