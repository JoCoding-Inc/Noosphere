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

interface Props {
  posts: Partial<Record<Platform, SocialPost[]>>
  report: ReportJSON | null | undefined
}

export function SimulationAnalytics({ posts, report }: Props) {
  const allPosts: SocialPost[] = useMemo(
    () => Object.values(posts).flatMap(list => list ?? []),
    [posts]
  )

  // 감성 도넛 데이터
  const sentimentData = useMemo(() => {
    if (!report?.segments) return []
    const counts: Record<string, number> = {}
    for (const seg of report.segments) {
      counts[seg.sentiment] = (counts[seg.sentiment] ?? 0) + 1
    }
    return Object.entries(counts)
      .map(([name, value]) => ({ name, value }))
      .sort((a, b) => SENTIMENT_ORDER.indexOf(a.name) - SENTIMENT_ORDER.indexOf(b.name))
  }, [report])

  // Criticism 비중 데이터
  const criticismData = useMemo(() => {
    if (!report?.criticism_clusters) return []
    return [...report.criticism_clusters]
      .sort((a, b) => b.count - a.count)
      .slice(0, 6)
      .map(c => ({ name: c.theme, count: c.count }))
  }, [report])

  // 라운드별 활동량 데이터
  const roundData = useMemo(() => {
    const counts: Record<number, number> = {}
    for (const p of allPosts) {
      counts[p.round_num] = (counts[p.round_num] ?? 0) + 1
    }
    return Object.entries(counts)
      .sort(([a], [b]) => Number(a) - Number(b))
      .map(([round, count]) => ({ round: `R${round}`, count }))
  }, [allPosts])

  // 플랫폼별 참여도 데이터
  const platformData = useMemo(() => {
    return (Object.keys(posts) as Platform[])
      .map(platform => ({
        name: PLATFORM_SHORT_LABELS[platform] ?? platform,
        count: posts[platform]?.length ?? 0,
        color: PLATFORM_COLORS[platform] ?? '#64748b',
      }))
      .filter(d => d.count > 0)
      .sort((a, b) => b.count - a.count)
  }, [posts])

  const hasData = sentimentData.length > 0 || criticismData.length > 0 || roundData.length > 0 || platformData.length > 0

  if (!hasData) return null

  return (
    <div style={{ marginTop: 32 }}>
      <div style={{ borderTop: '1px solid #e2e8f0', paddingTop: 28 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 20 }}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#6366f1" strokeWidth="2" aria-hidden="true">
            <line x1="18" y1="20" x2="18" y2="10"/>
            <line x1="12" y1="20" x2="12" y2="4"/>
            <line x1="6" y1="20" x2="6" y2="14"/>
          </svg>
          <span style={{ fontSize: 16, fontWeight: 700, color: '#6366f1' }}>Analytics</span>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 16, marginBottom: 16 }}>

          {/* 감성 도넛 */}
          {sentimentData.length > 0 && (
            <div style={{ background: '#fff', border: '1px solid #e2e8f0', borderRadius: 10, padding: 16, boxShadow: '0 1px 3px rgba(0,0,0,0.04)' }}>
              <p style={{ fontSize: 12, fontWeight: 600, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 12 }}>
                Segment 감성 분포
              </p>
              <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
                <div style={{ width: 100, height: 100, flexShrink: 0 }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie data={sentimentData} cx="50%" cy="50%" innerRadius={28} outerRadius={44} dataKey="value" strokeWidth={0}>
                        {sentimentData.map((entry) => (
                          <Cell key={entry.name} fill={SENTIMENT_COLORS[entry.name] ?? '#94a3b8'} />
                        ))}
                      </Pie>
                      <Tooltip />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                  {sentimentData.map(d => (
                    <div key={d.name} style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: '#475569' }}>
                      <span style={{ width: 10, height: 10, borderRadius: '50%', background: SENTIMENT_COLORS[d.name] ?? '#94a3b8', flexShrink: 0, display: 'inline-block' }} />
                      <span style={{ textTransform: 'capitalize' }}>{d.name}</span>
                      <span style={{ color: '#94a3b8' }}>{d.value}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* 라운드별 활동량 */}
          {roundData.length > 0 && (
            <div style={{ background: '#fff', border: '1px solid #e2e8f0', borderRadius: 10, padding: 16, boxShadow: '0 1px 3px rgba(0,0,0,0.04)' }}>
              <p style={{ fontSize: 12, fontWeight: 600, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 12 }}>
                라운드별 활동량
              </p>
              <ResponsiveContainer width="100%" height={100}>
                <BarChart data={roundData} margin={{ top: 0, right: 0, bottom: 0, left: -20 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
                  <XAxis dataKey="round" tick={{ fontSize: 11, fill: '#94a3b8' }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fontSize: 11, fill: '#94a3b8' }} axisLine={false} tickLine={false} />
                  <Tooltip cursor={{ fill: '#f8fafc' }} />
                  <Bar dataKey="count" fill="#6366f1" radius={[3, 3, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* Criticism 비중 */}
          {criticismData.length > 0 && (
            <div style={{ background: '#fff', border: '1px solid #e2e8f0', borderRadius: 10, padding: 16, boxShadow: '0 1px 3px rgba(0,0,0,0.04)' }}>
              <p style={{ fontSize: 12, fontWeight: 600, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 12 }}>
                Criticism 비중
              </p>
              <ResponsiveContainer width="100%" height={Math.max(100, criticismData.length * 26)}>
                <BarChart data={criticismData} layout="vertical" margin={{ top: 0, right: 8, bottom: 0, left: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" horizontal={false} />
                  <XAxis type="number" tick={{ fontSize: 11, fill: '#94a3b8' }} axisLine={false} tickLine={false} />
                  <YAxis type="category" dataKey="name" width={110} tick={{ fontSize: 11, fill: '#64748b' }} axisLine={false} tickLine={false} />
                  <Tooltip cursor={{ fill: '#fff1f2' }} />
                  <Bar dataKey="count" fill="#ef4444" radius={[0, 3, 3, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* 플랫폼별 참여도 */}
          {platformData.length > 0 && (
            <div style={{ background: '#fff', border: '1px solid #e2e8f0', borderRadius: 10, padding: 16, boxShadow: '0 1px 3px rgba(0,0,0,0.04)' }}>
              <p style={{ fontSize: 12, fontWeight: 600, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 12 }}>
                플랫폼별 참여도
              </p>
              <ResponsiveContainer width="100%" height={Math.max(100, platformData.length * 26)}>
                <BarChart data={platformData} layout="vertical" margin={{ top: 0, right: 8, bottom: 0, left: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" horizontal={false} />
                  <XAxis type="number" tick={{ fontSize: 11, fill: '#94a3b8' }} axisLine={false} tickLine={false} />
                  <YAxis type="category" dataKey="name" width={50} tick={{ fontSize: 11, fill: '#64748b' }} axisLine={false} tickLine={false} />
                  <Tooltip cursor={{ fill: '#f8fafc' }} />
                  <Bar dataKey="count" radius={[0, 3, 3, 0]}>
                    {platformData.map((entry) => (
                      <Cell key={entry.name} fill={entry.color} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}

        </div>
      </div>
    </div>
  )
}
