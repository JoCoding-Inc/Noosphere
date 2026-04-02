import { useMemo } from 'react'
import {
  PieChart, Pie, Cell, Tooltip, ResponsiveContainer, Legend,
  BarChart, Bar, XAxis, YAxis, CartesianGrid, LabelList,
} from 'recharts'
import type { Platform, SocialPost, ReportJSON, Persona } from '../types'

const PLATFORM_SHORT_LABELS: Record<Platform, string> = {
  hackernews:      'HN',
  producthunt:     'PH',
  indiehackers:    'IH',
  reddit_startups: 'Reddit',
  linkedin:        'LinkedIn',
}

const SENTIMENT_ORDER = ['positive', 'neutral', 'negative', 'constructive']

const SENTIMENT_COLORS: Record<string, string> = {
  positive:     '#22c55e',
  neutral:      '#94a3b8',
  negative:     '#ef4444',
  constructive: '#3b82f6',
}

const SENTIMENT_LABELS: Record<string, string> = {
  positive:     'Positive',
  neutral:      'Neutral',
  negative:     'Negative',
  constructive: 'Constructive',
  engagement:   'Engagement',
}

export interface RoundStat {
  round: number
  totalActiveAgents: number
  totalNewPosts: number
  totalNewComments: number
}

interface Props {
  posts: Partial<Record<Platform, SocialPost[]>>
  report: ReportJSON | null | undefined
  roundStats?: RoundStat[]
  personas?: Partial<Record<string, Persona[]>>
  segmentDistribution?: Record<string, number>
}

const SEGMENT_COLORS: Record<string, string> = {
  developer: '#3b82f6',
  investor: '#10b981',
  founder: '#f59e0b',
  skeptic: '#ef4444',
  early_adopter: '#8b5cf6',
  pm: '#06b6d4',
  designer: '#ec4899',
  marketer: '#f97316',
  executive: '#6b7280',
  other: '#94a3b8',
  analyst: '#7c3aed',
}

const SEGMENT_LABELS: Record<string, string> = {
  developer: 'Developer',
  investor: 'Investor',
  founder: 'Founder',
  skeptic: 'Skeptic',
  early_adopter: 'Early Adopter',
  pm: 'PM',
  designer: 'Designer',
  marketer: 'Marketer',
  executive: 'Executive',
  other: 'Other',
  analyst: 'Analyst',
}

export function SimulationAnalytics({ posts, report, roundStats, personas, segmentDistribution }: Props) {
  const allPosts: SocialPost[] = useMemo(
    () => Object.values(posts).flatMap(list => list ?? []),
    [posts]
  )

  // 포스트 단위 감성 집계
  const sentimentData = useMemo(() => {
    const counts: Record<string, number> = { positive: 0, neutral: 0, negative: 0, constructive: 0 }
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

  // Praise clusters
  const praiseData = useMemo(() => {
    if (!report?.praise_clusters) return []
    return [...report.praise_clusters]
      .sort((a, b) => b.count - a.count)
      .slice(0, 6)
      .map(c => ({
        name: c.theme.length > 22 ? c.theme.slice(0, 20) + '\u2026' : c.theme,
        fullName: c.theme,
        count: c.count,
        examples: c.examples,
      }))
  }, [report])

  // Platform reception stacked bar data
  const platformReceptionData = useMemo(() => {
    if (!report?.platform_summaries) return []
    const entries = Object.entries(report.platform_summaries)
    if (entries.length < 2) return []
    return entries.map(([name, data]) => ({
      name: (PLATFORM_SHORT_LABELS as Record<string, string>)[name] ?? name,
      positive: data.total > 0 ? Math.round(data.positive / data.total * 100) : 0,
      neutral: data.total > 0 ? Math.round(data.neutral / data.total * 100) : 0,
      negative: data.total > 0 ? Math.round(data.negative / data.total * 100) : 0,
    }))
  }, [report])

  // ── Persona demographics ────────────────────────────────────────────
  const allPersonas = useMemo(() => {
    if (!personas) return []
    return Object.values(personas).flatMap(list => list ?? [])
  }, [personas])

  const seniorityData = useMemo(() => {
    if (allPersonas.length === 0) return []
    const counts: Record<string, number> = {}
    for (const p of allPersonas) {
      if (p.seniority) counts[p.seniority] = (counts[p.seniority] ?? 0) + 1
    }
    return Object.entries(counts)
      .sort((a, b) => b[1] - a[1])
      .map(([name, count]) => ({ name, count }))
  }, [allPersonas])

  const topAffiliations = useMemo(() => {
    if (allPersonas.length === 0) return []
    const counts: Record<string, number> = {}
    for (const p of allPersonas) {
      if (p.affiliation) counts[p.affiliation] = (counts[p.affiliation] ?? 0) + 1
    }
    return Object.entries(counts)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 5)
      .map(([name, count]) => ({ name, count }))
  }, [allPersonas])

  const mbtiData = useMemo(() => {
    if (allPersonas.length === 0) return []
    const counts: Record<string, number> = {}
    for (const p of allPersonas) {
      if (p.mbti) counts[p.mbti] = (counts[p.mbti] ?? 0) + 1
    }
    return Object.entries(counts)
      .map(([name, count]) => ({ name, count }))
      .sort((a, b) => b.count - a.count)
      .slice(0, 8)
  }, [allPersonas])

  const generationData = useMemo(() => {
    if (allPersonas.length === 0) return []
    const ORDER = ['Gen Z', 'Millennial', 'Gen X', 'Boomer']
    const counts: Record<string, number> = {}
    for (const p of allPersonas) {
      if (p.generation) counts[p.generation] = (counts[p.generation] ?? 0) + 1
    }
    return ORDER
      .filter(g => counts[g])
      .map(name => ({ name, count: counts[name] }))
  }, [allPersonas])

  const avgTraits = useMemo(() => {
    if (allPersonas.length === 0) return null
    let skepticism = 0, commercial = 0, innovation = 0
    let sCount = 0, cCount = 0, iCount = 0
    for (const p of allPersonas) {
      if (p.skepticism != null) { skepticism += p.skepticism; sCount++ }
      if (p.commercial_focus != null) { commercial += p.commercial_focus; cCount++ }
      if (p.innovation_openness != null) { innovation += p.innovation_openness; iCount++ }
    }
    if (sCount === 0 && cCount === 0 && iCount === 0) return null
    return {
      skepticism: sCount > 0 ? skepticism / sCount : 0,
      commercial_focus: cCount > 0 ? commercial / cCount : 0,
      innovation_openness: iCount > 0 ? innovation / iCount : 0,
    }
  }, [allPersonas])

  const hasPersonaData = allPersonas.length > 0

  // ── ProductHunt Ratings ───────────────────────────────────────────
  const phRatingsData = useMemo(() => {
    const ratings = report?.producthunt_ratings
    if (!ratings?.distribution) return []
    return [1, 2, 3, 4, 5].map(star => ({
      name: `${star}\u2605`,
      count: ratings.distribution[String(star)] || 0,
    }))
  }, [report])

  // ── ProductHunt Pros & Cons ───────────────────────────────────────
  const phProsConsData = useMemo(() => {
    const pc = report?.producthunt_pros_cons
    if (!pc) return null
    return { pros: pc.top_pros || [], cons: pc.top_cons || [] }
  }, [report])

  const hasData = sentimentData.length > 0 || criticismData.length > 0
    || praiseData.length > 0 || platformReceptionData.length > 0
    || hasPersonaData
    || phRatingsData.some(d => d.count > 0)
    || phProsConsData !== null

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
        {report?.early_exit_round != null && (
          <div style={{
            display: 'inline-flex', alignItems: 'center', gap: 6,
            padding: '4px 10px', borderRadius: 8,
            background: '#dcfce7', color: '#15803d',
            fontSize: 11, fontWeight: 600, marginLeft: 8,
          }}>
            ⚡ Early consensus at round {report.early_exit_round}
          </div>
        )}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 16, marginBottom: 16, alignItems: 'start' }}>

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

        {/* What People Loved (praise clusters) */}
        {praiseData.length > 0 && (
          <div style={{ background: '#fff', border: '1px solid #dcfce7', borderRadius: 10, padding: 16, boxShadow: '0 1px 3px rgba(0,0,0,0.04)' }}>
            <p style={{ fontSize: 12, fontWeight: 600, color: '#22c55e', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 12 }}>
              What People Loved
            </p>
            <ResponsiveContainer width="100%" height={Math.max(120, praiseData.length * 36)}>
              <BarChart data={praiseData} layout="vertical" margin={{ top: 0, right: 8, bottom: 0, left: 0 }}>
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
                  cursor={{ fill: '#f0fdf4' }}
                  formatter={(v) => [v, 'mentions']}
                  labelFormatter={(label) => {
                    const item = praiseData.find(c => c.name === label)
                    return item?.fullName ?? label
                  }}
                />
                <Bar dataKey="count" fill="#22c55e" radius={[0, 3, 3, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}

        {/* Platform Reception (stacked bar + verdict badges) */}
        {platformReceptionData.length > 0 && (
          <div style={{ background: '#fff', border: '1px solid #e2e8f0', borderRadius: 10, padding: 16, boxShadow: '0 1px 3px rgba(0,0,0,0.04)' }}>
            <p style={{ fontSize: 12, fontWeight: 600, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 12 }}>
              Platform Reception
            </p>
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={platformReceptionData} margin={{ top: 0, right: 8, bottom: 0, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                <XAxis dataKey="name" tick={{ fontSize: 11, fill: '#64748b' }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fontSize: 11, fill: '#94a3b8' }} axisLine={false} tickLine={false} unit="%" />
                <Tooltip formatter={(v, name) => [`${v}%`, SENTIMENT_LABELS[name as string] ?? name]} />
                <Legend
                  formatter={(value) => SENTIMENT_LABELS[value as string] ?? value}
                  wrapperStyle={{ fontSize: 11 }}
                />
                <Bar dataKey="positive" stackId="a" fill="#22c55e" />
                <Bar dataKey="neutral" stackId="a" fill="#94a3b8" />
                <Bar dataKey="negative" stackId="a" fill="#ef4444" />
              </BarChart>
            </ResponsiveContainer>
            {/* Verdict badges per platform */}
            {report?.platform_summaries && (
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginTop: 12 }}>
                {Object.entries(report.platform_summaries).map(([name, data]) => {
                  const label = (PLATFORM_SHORT_LABELS as Record<string, string>)[name] ?? name
                  const verdict = data.verdict
                  if (!verdict) return null
                  const vLower = verdict.toLowerCase()
                  const bg = vLower.includes('positive') ? '#dcfce7'
                    : vLower.includes('negative') ? '#fee2e2'
                    : vLower.includes('skepti') ? '#ffedd5'
                    : '#f1f5f9'
                  const fg = vLower.includes('positive') ? '#15803d'
                    : vLower.includes('negative') ? '#b91c1c'
                    : vLower.includes('skepti') ? '#c2410c'
                    : '#475569'
                  return (
                    <span key={name} style={{
                      display: 'inline-flex', alignItems: 'center', gap: 4,
                      fontSize: 11, fontWeight: 600, padding: '3px 10px',
                      borderRadius: 10, background: bg, color: fg,
                    }}>
                      {label}: {verdict}
                    </span>
                  )
                })}
              </div>
            )}
          </div>
        )}

        {/* ProductHunt Ratings */}
        {phRatingsData.some(d => d.count > 0) && (
          <div style={{ background: '#fff', border: '1px solid #e2e8f0', borderRadius: 10, padding: 16, boxShadow: '0 1px 3px rgba(0,0,0,0.04)' }}>
            <p style={{ fontSize: 12, fontWeight: 600, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 12 }}>
              ProductHunt Ratings
            </p>
            <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 12 }}>
              <span style={{ fontSize: 28, fontWeight: 700, color: '#f59e0b' }}>
                {report?.producthunt_ratings?.avg_rating?.toFixed(1) ?? '-'}
                <span style={{ fontSize: 14, fontWeight: 400, color: '#94a3b8' }}> / 5</span>
              </span>
              <span style={{ fontSize: 11, color: '#94a3b8' }}>
                {report?.producthunt_ratings?.total_reviews ?? 0} reviews
              </span>
            </div>
            <ResponsiveContainer width="100%" height={140}>
              <BarChart data={phRatingsData} layout="vertical" margin={{ top: 0, right: 8, bottom: 0, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" horizontal={false} />
                <XAxis type="number" tick={{ fontSize: 11, fill: '#94a3b8' }} axisLine={false} tickLine={false} allowDecimals={false} />
                <YAxis
                  type="category"
                  dataKey="name"
                  width={40}
                  tick={{ fontSize: 12, fill: '#64748b' }}
                  axisLine={false}
                  tickLine={false}
                />
                <Tooltip cursor={{ fill: '#fef3c7' }} />
                <Bar dataKey="count" fill="#f59e0b" name="Reviews" radius={[0, 3, 3, 0]}>
                  <LabelList dataKey="count" position="right" style={{ fontSize: 11, fill: '#64748b' }} />
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}

        {/* ProductHunt Pros & Cons */}
        {phProsConsData !== null && (phProsConsData.pros.length > 0 || phProsConsData.cons.length > 0) && (
          <div style={{ background: '#fff', border: '1px solid #e2e8f0', borderRadius: 10, padding: 16, boxShadow: '0 1px 3px rgba(0,0,0,0.04)' }}>
            <p style={{ fontSize: 12, fontWeight: 600, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 12 }}>
              ProductHunt Pros &amp; Cons
            </p>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
              {/* Pros */}
              <div>
                <p style={{ fontSize: 11, fontWeight: 600, color: '#10b981', marginBottom: 8 }}>Pros</p>
                {phProsConsData.pros.slice(0, 5).map((item, idx) => (
                  <div key={idx} style={{ marginBottom: 6 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, marginBottom: 2 }}>
                      <span style={{ color: '#334155', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', maxWidth: '70%' }}>{item.theme}</span>
                      <span style={{ color: '#64748b', fontWeight: 600 }}>{item.count}</span>
                    </div>
                    <div style={{ height: 6, background: '#f1f5f9', borderRadius: 3 }}>
                      <div style={{
                        height: '100%',
                        width: `${Math.min(100, (item.count / Math.max(...phProsConsData.pros.map(p => p.count), 1)) * 100)}%`,
                        background: '#10b981',
                        borderRadius: 3,
                      }} />
                    </div>
                  </div>
                ))}
              </div>
              {/* Cons */}
              <div>
                <p style={{ fontSize: 11, fontWeight: 600, color: '#f87171', marginBottom: 8 }}>Cons</p>
                {phProsConsData.cons.slice(0, 5).map((item, idx) => (
                  <div key={idx} style={{ marginBottom: 6 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, marginBottom: 2 }}>
                      <span style={{ color: '#334155', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', maxWidth: '70%' }}>{item.theme}</span>
                      <span style={{ color: '#64748b', fontWeight: 600 }}>{item.count}</span>
                    </div>
                    <div style={{ height: 6, background: '#f1f5f9', borderRadius: 3 }}>
                      <div style={{
                        height: '100%',
                        width: `${Math.min(100, (item.count / Math.max(...phProsConsData.cons.map(c => c.count), 1)) * 100)}%`,
                        background: '#f87171',
                        borderRadius: 3,
                      }} />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

      </div>

      {/* Participant Profile — full-width horizontal layout */}
      {hasPersonaData && (
        <div style={{ background: '#fff', border: '1px solid #e2e8f0', borderRadius: 10, padding: 16, boxShadow: '0 1px 3px rgba(0,0,0,0.04)', marginBottom: 16 }}>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, marginBottom: 16 }}>
            <p style={{ fontSize: 12, fontWeight: 600, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.5px', margin: 0 }}>
              Participant Profile
            </p>
            <span style={{ fontSize: 20, fontWeight: 700, color: '#1e293b' }}>{allPersonas.length}</span>
            <span style={{ fontSize: 12, color: '#94a3b8' }}>total participants</span>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 16 }}>

            {/* Seniority */}
            {seniorityData.length > 0 && (
              <div style={{ display: 'flex', flexDirection: 'column', minHeight: 160 }}>
                <p style={{ fontSize: 11, color: '#64748b', fontWeight: 600, marginBottom: 8 }}>Seniority</p>
                <div style={{ flex: 1, minHeight: 0 }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={seniorityData} layout="vertical" margin={{ top: 0, right: 8, bottom: 0, left: 0 }}>
                      <XAxis type="number" tick={{ fontSize: 10, fill: '#94a3b8' }} axisLine={false} tickLine={false} allowDecimals={false} />
                      <YAxis type="category" dataKey="name" width={72} tick={{ fontSize: 10, fill: '#64748b' }} axisLine={false} tickLine={false} />
                      <Tooltip cursor={{ fill: '#f8fafc' }} formatter={(v) => [v, 'count']} />
                      <Bar dataKey="count" fill="#8b5cf6" radius={[0, 3, 3, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>
            )}

            {/* MBTI */}
            {mbtiData.length > 0 && (
              <div style={{ display: 'flex', flexDirection: 'column', minHeight: 160 }}>
                <p style={{ fontSize: 11, color: '#64748b', fontWeight: 600, marginBottom: 8 }}>MBTI</p>
                <div style={{ flex: 1, minHeight: 0 }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={mbtiData} layout="vertical" margin={{ top: 0, right: 8, bottom: 0, left: 0 }}>
                      <XAxis type="number" tick={{ fontSize: 10, fill: '#94a3b8' }} axisLine={false} tickLine={false} allowDecimals={false} />
                      <YAxis type="category" dataKey="name" width={48} tick={{ fontSize: 10, fill: '#64748b' }} axisLine={false} tickLine={false} />
                      <Tooltip cursor={{ fill: '#f8fafc' }} formatter={(v) => [v, 'count']} />
                      <Bar dataKey="count" fill="#06b6d4" radius={[0, 3, 3, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>
            )}

            {/* Generation */}
            {generationData.length > 0 && (
              <div style={{ display: 'flex', flexDirection: 'column', minHeight: 160 }}>
                <p style={{ fontSize: 11, color: '#64748b', fontWeight: 600, marginBottom: 8 }}>Generation</p>
                <div style={{ flex: 1, minHeight: 0 }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={generationData} layout="vertical" margin={{ top: 0, right: 8, bottom: 0, left: 0 }}>
                      <XAxis type="number" tick={{ fontSize: 10, fill: '#94a3b8' }} axisLine={false} tickLine={false} allowDecimals={false} />
                      <YAxis type="category" dataKey="name" width={72} tick={{ fontSize: 10, fill: '#64748b' }} axisLine={false} tickLine={false} />
                      <Tooltip cursor={{ fill: '#f8fafc' }} formatter={(v) => [v, 'count']} />
                      <Bar dataKey="count" fill="#f59e0b" radius={[0, 3, 3, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>
            )}

            {/* Affiliations */}
            {topAffiliations.length > 0 && (
              <div>
                <p style={{ fontSize: 11, color: '#64748b', fontWeight: 600, marginBottom: 8 }}>Top Affiliations</p>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
                  {topAffiliations.map(a => (
                    <div key={a.name} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span style={{ fontSize: 11, color: '#475569', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '75%' }}>{a.name}</span>
                      <span style={{ fontSize: 11, fontWeight: 600, color: '#64748b' }}>{a.count}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Average Traits */}
            {avgTraits && (
              <div>
                <p style={{ fontSize: 11, color: '#64748b', fontWeight: 600, marginBottom: 8 }}>Avg Traits (1–10)</p>
                {[
                  { label: 'Skepticism', value: avgTraits.skepticism, color: '#f59e0b' },
                  { label: 'Commercial Focus', value: avgTraits.commercial_focus, color: '#3b82f6' },
                  { label: 'Innovation', value: avgTraits.innovation_openness, color: '#22c55e' },
                ].map(t => (
                  <div key={t.label} style={{ marginBottom: 8 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, marginBottom: 3 }}>
                      <span style={{ color: '#64748b' }}>{t.label}</span>
                      <span style={{ color: '#94a3b8' }}>{t.value.toFixed(1)}</span>
                    </div>
                    <div style={{ height: 5, borderRadius: 3, background: '#f1f5f9', overflow: 'hidden' }}>
                      <div style={{ height: '100%', borderRadius: 3, background: t.color, width: `${(t.value / 10) * 100}%` }} />
                    </div>
                  </div>
                ))}
              </div>
            )}

          </div>
        </div>
      )}

    </div>
  )
}
