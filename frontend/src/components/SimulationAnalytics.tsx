import { useMemo } from 'react'
import {
  PieChart, Pie, Cell, Tooltip, ResponsiveContainer,
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
} from 'recharts'
import type { Platform, SocialPost, ReportJSON } from '../types'
import { PLATFORM_COLORS } from '../constants'

const PLATFORM_SHORT_LABELS: Record<Platform, string> = {
  hackernews:      'HN',
  producthunt:     'PH',
  indiehackers:    'IH',
  reddit_startups: 'Reddit',
  linkedin:        'LinkedIn',
}

const SENTIMENT_ORDER = ['positive', 'neutral', 'negative']

const SENTIMENT_COLORS: Record<string, string> = {
  positive: '#22c55e',
  neutral:  '#94a3b8',
  negative: '#ef4444',
}

const SENTIMENT_LABELS: Record<string, string> = {
  positive: 'Positive',
  neutral:  'Neutral',
  negative: 'Negative',
}

interface Props {
  posts: Partial<Record<Platform, SocialPost[]>>
  report: ReportJSON | null | undefined
}

export function SimulationAnalytics({ posts, report }: Props) {
  const allPosts: SocialPost[] = useMemo(
    () => Object.values(posts).flatMap(list => list ?? []),
    [posts]
  )

  // 포스트 단위 감성 집계
  const sentimentData = useMemo(() => {
    const counts: Record<string, number> = { positive: 0, neutral: 0, negative: 0 }
    for (const p of allPosts) {
      if (p.sentiment && p.sentiment in counts) counts[p.sentiment]++
    }
    return SENTIMENT_ORDER
      .map(name => ({ name, value: counts[name] }))
      .filter(d => d.value > 0)
  }, [allPosts])

  const totalSentimentPosts = useMemo(
    () => sentimentData.reduce((s, d) => s + d.value, 0),
    [sentimentData]
  )

  // Criticism 비중 데이터
  const criticismData = useMemo(() => {
    if (!report?.criticism_clusters) return []
    return [...report.criticism_clusters]
      .sort((a, b) => b.count - a.count)
      .slice(0, 6)
      .map(c => ({
        name: c.theme.length > 22 ? c.theme.slice(0, 20) + '…' : c.theme,
        fullName: c.theme,
        count: c.count,
      }))
  }, [report])

  // 플랫폼별 평균 콘텐츠 길이 (참여 깊이 지표)
  const platformDepthData = useMemo(() => {
    return (Object.keys(posts) as Platform[])
      .map(platform => {
        const list = posts[platform] ?? []
        const avgLen = list.length === 0
          ? 0
          : Math.round(list.reduce((sum, p) => sum + p.content.length, 0) / list.length)
        return {
          name: PLATFORM_SHORT_LABELS[platform] ?? platform,
          avgLen,
          color: PLATFORM_COLORS[platform] ?? '#64748b',
        }
      })
      .filter(d => d.avgLen > 0)
      .sort((a, b) => b.avgLen - a.avgLen)
  }, [posts])

  const hasData = sentimentData.length > 0 || criticismData.length > 0 || platformDepthData.length > 0

  if (!hasData) return null

  return (
    <div style={{ marginBottom: 32 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 20 }}>
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#6366f1" strokeWidth="2" aria-hidden="true">
          <line x1="18" y1="20" x2="18" y2="10"/>
          <line x1="12" y1="20" x2="12" y2="4"/>
          <line x1="6" y1="20" x2="6" y2="14"/>
        </svg>
        <span style={{ fontSize: 16, fontWeight: 700, color: '#6366f1' }}>Simulation Analytics</span>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 16, marginBottom: 16 }}>

        {/* Post-level Sentiment Distribution */}
        {sentimentData.length > 0 && (
          <div style={{ background: '#fff', border: '1px solid #e2e8f0', borderRadius: 10, padding: 16, boxShadow: '0 1px 3px rgba(0,0,0,0.04)' }}>
            <p style={{ fontSize: 12, fontWeight: 600, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 12 }}>
              Post Sentiment
            </p>
            <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
              <div style={{ width: 90, height: 90, flexShrink: 0 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie data={sentimentData} cx="50%" cy="50%" innerRadius={24} outerRadius={40} dataKey="value" strokeWidth={0}>
                      {sentimentData.map((entry) => (
                        <Cell key={entry.name} fill={SENTIMENT_COLORS[entry.name] ?? '#94a3b8'} />
                      ))}
                    </Pie>
                    <Tooltip formatter={(v, name) => [v, SENTIMENT_LABELS[name as string] ?? name]} />
                  </PieChart>
                </ResponsiveContainer>
              </div>
              <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 8 }}>
                {sentimentData.map(d => {
                  const pct = totalSentimentPosts > 0 ? Math.round(d.value / totalSentimentPosts * 100) : 0
                  return (
                    <div key={d.name}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, marginBottom: 3 }}>
                        <span style={{ color: SENTIMENT_COLORS[d.name] ?? '#94a3b8', fontWeight: 600 }}>
                          {SENTIMENT_LABELS[d.name]}
                        </span>
                        <span style={{ color: '#94a3b8' }}>{d.value} ({pct}%)</span>
                      </div>
                      <div style={{ height: 5, borderRadius: 3, background: '#f1f5f9', overflow: 'hidden' }}>
                        <div style={{ height: '100%', width: `${pct}%`, background: SENTIMENT_COLORS[d.name] ?? '#94a3b8', borderRadius: 3 }} />
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>
          </div>
        )}


        {/* Criticism 비중 */}
        {criticismData.length > 0 && (
          <div style={{ background: '#fff', border: '1px solid #e2e8f0', borderRadius: 10, padding: 16, boxShadow: '0 1px 3px rgba(0,0,0,0.04)' }}>
            <p style={{ fontSize: 12, fontWeight: 600, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 12 }}>
              Criticism Breakdown
            </p>
            <ResponsiveContainer width="100%" height={Math.max(120, criticismData.length * 36)}>
              <BarChart data={criticismData} layout="vertical" margin={{ top: 0, right: 8, bottom: 0, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" horizontal={false} />
                <XAxis type="number" tick={{ fontSize: 11, fill: '#94a3b8' }} axisLine={false} tickLine={false} />
                <YAxis
                  type="category"
                  dataKey="name"
                  width={140}
                  tick={{ fontSize: 11, fill: '#64748b' }}
                  axisLine={false}
                  tickLine={false}
                />
                <Tooltip
                  cursor={{ fill: '#fff1f2' }}
                  formatter={(v) => [v, 'mentions']}
                  labelFormatter={(label) => {
                    const item = criticismData.find(c => c.name === label)
                    return item?.fullName ?? label
                  }}
                />
                <Bar dataKey="count" fill="#ef4444" radius={[0, 3, 3, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}

        {/* 플랫폼별 의견 깊이 (평균 콘텐츠 길이) */}
        {platformDepthData.length > 0 && (
          <div style={{ background: '#fff', border: '1px solid #e2e8f0', borderRadius: 10, padding: 16, boxShadow: '0 1px 3px rgba(0,0,0,0.04)' }}>
            <p style={{ fontSize: 12, fontWeight: 600, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 12 }}>
              Avg. Response Depth
            </p>
            <p style={{ fontSize: 11, color: '#cbd5e1', marginBottom: 10 }}>Avg. content length (chars)</p>
            <ResponsiveContainer width="100%" height={Math.max(100, platformDepthData.length * 28)}>
              <BarChart data={platformDepthData} layout="vertical" margin={{ top: 0, right: 8, bottom: 0, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" horizontal={false} />
                <XAxis type="number" tick={{ fontSize: 11, fill: '#94a3b8' }} axisLine={false} tickLine={false} />
                <YAxis type="category" dataKey="name" width={50} tick={{ fontSize: 11, fill: '#64748b' }} axisLine={false} tickLine={false} />
                <Tooltip cursor={{ fill: '#f8fafc' }} formatter={(v) => [`${v} chars`, 'Avg. length']} />
                <Bar dataKey="avgLen" radius={[0, 3, 3, 0]}>
                  {platformDepthData.map((entry) => (
                    <Cell key={entry.name} fill={entry.color} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}

      </div>
    </div>
  )
}
