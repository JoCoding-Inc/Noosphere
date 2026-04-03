import { useMemo } from 'react'
import {
  PieChart, Pie, Cell, Tooltip, ResponsiveContainer, Legend,
  BarChart, Bar, XAxis, YAxis, CartesianGrid, LabelList,
} from 'recharts'
import { t } from '../tokens'
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
  positive:     t.color.success,
  neutral:      t.color.textMuted,
  negative:     t.color.danger,
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

export function SimulationAnalytics({ posts, report, personas }: Props) {
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
      positive: data.total > 0 ? Math.round((data.positive ?? 0) / data.total * 100) : 0,
      neutral: data.total > 0 ? Math.round((data.neutral ?? 0) / data.total * 100) : 0,
      negative: data.total > 0 ? Math.round((data.negative ?? 0) / data.total * 100) : 0,
      constructive: data.total > 0 ? Math.round((data.constructive ?? 0) / data.total * 100) : 0,
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
      <div style={{ display: 'flex', alignItems: 'center', gap: t.space[2], marginBottom: t.space[5] }}>
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke={t.color.primary} strokeWidth="2" aria-hidden="true">
          <line x1="18" y1="20" x2="18" y2="10"/>
          <line x1="12" y1="20" x2="12" y2="4"/>
          <line x1="6" y1="20" x2="6" y2="14"/>
        </svg>
        <span style={{ fontSize: t.font.size.xl, fontWeight: t.font.weight.bold, color: t.color.primary }}>Simulation Analytics</span>
        {report?.early_exit_round != null && (
          <div style={{
            display: 'inline-flex', alignItems: 'center', gap: t.space[1],
            padding: '4px 10px', borderRadius: t.radius.md,
            background: '#dcfce7', color: '#15803d',
            fontSize: t.font.size.xs, fontWeight: t.font.weight.semibold, marginLeft: t.space[2],
          }}>
            ⚡ Early consensus at round {report.early_exit_round}
          </div>
        )}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: t.space[4], marginBottom: t.space[4] }}>

        {/* Post-level Sentiment Distribution */}
        {sentimentData.length > 0 && (
          <div style={{ background: t.color.bgPage, border: `1px solid ${t.color.border}`, borderRadius: t.radius.lg, padding: t.space[4], boxShadow: '0 1px 3px rgba(0,0,0,0.04)', display: 'flex', flexDirection: 'column' }}>
            <p style={{ fontSize: t.font.size.sm, fontWeight: t.font.weight.semibold, color: t.color.textMuted, textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: t.space[3] }}>
              Post Sentiment
            </p>
            <div style={{ flex: 1, minHeight: 0, display: 'flex', alignItems: 'center', gap: t.space[4] }}>
              <div style={{ width: 90, height: 90, flexShrink: 0 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie data={sentimentData} cx="50%" cy="50%" innerRadius={24} outerRadius={40} dataKey="value" strokeWidth={0}>
                      {sentimentData.map((entry) => (
                        <Cell key={entry.name} fill={SENTIMENT_COLORS[entry.name] ?? t.color.textMuted} />
                      ))}
                    </Pie>
                    <Tooltip formatter={(v, name) => [v, SENTIMENT_LABELS[name as string] ?? name]} />
                  </PieChart>
                </ResponsiveContainer>
              </div>
              <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: t.space[2] }}>
                {sentimentData.map(d => {
                  const pct = totalSentimentPosts > 0 ? Math.round(d.value / totalSentimentPosts * 100) : 0
                  return (
                    <div key={d.name}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: t.font.size.xs, marginBottom: t.space[1] }}>
                        <span style={{ color: SENTIMENT_COLORS[d.name] ?? t.color.textMuted, fontWeight: t.font.weight.semibold }}>
                          {SENTIMENT_LABELS[d.name]}
                        </span>
                        <span style={{ color: t.color.textMuted }}>{d.value} ({pct}%)</span>
                      </div>
                      <div style={{ height: 5, borderRadius: 3, background: t.color.bgSubtle, overflow: 'hidden' }}>
                        <div style={{ height: '100%', width: `${pct}%`, background: SENTIMENT_COLORS[d.name] ?? t.color.textMuted, borderRadius: 3 }} />
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
          <div style={{ background: t.color.bgPage, border: `1px solid ${t.color.border}`, borderRadius: t.radius.lg, padding: t.space[4], boxShadow: '0 1px 3px rgba(0,0,0,0.04)', display: 'flex', flexDirection: 'column' }}>
            <p style={{ fontSize: t.font.size.sm, fontWeight: t.font.weight.semibold, color: t.color.textMuted, textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: t.space[3] }}>
              Criticism Breakdown
            </p>
            <div style={{ flex: 1, minHeight: 120 }}>
              <ResponsiveContainer width="100%" height="100%">
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
          </div>
        )}

        {/* What People Loved (praise clusters) */}
        {praiseData.length > 0 && (
          <div style={{ background: t.color.bgPage, border: '1px solid #dcfce7', borderRadius: t.radius.lg, padding: t.space[4], boxShadow: '0 1px 3px rgba(0,0,0,0.04)', display: 'flex', flexDirection: 'column' }}>
            <p style={{ fontSize: t.font.size.sm, fontWeight: t.font.weight.semibold, color: t.color.success, textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: t.space[3] }}>
              What People Loved
            </p>
            <div style={{ flex: 1, minHeight: 120 }}>
              <ResponsiveContainer width="100%" height="100%">
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
          </div>
        )}

        {/* Platform Reception (stacked bar + verdict badges) */}
        {platformReceptionData.length > 0 && (
          <div style={{ background: t.color.bgPage, border: `1px solid ${t.color.border}`, borderRadius: t.radius.lg, padding: t.space[4], boxShadow: '0 1px 3px rgba(0,0,0,0.04)', display: 'flex', flexDirection: 'column' }}>
            <p style={{ fontSize: t.font.size.sm, fontWeight: t.font.weight.semibold, color: t.color.textMuted, textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: t.space[3] }}>
              Platform Reception
            </p>
            <div style={{ flex: 1, minHeight: 120 }}>
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={platformReceptionData} margin={{ top: 0, right: 8, bottom: 0, left: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                  <XAxis dataKey="name" tick={{ fontSize: 11, fill: '#64748b' }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fontSize: 11, fill: '#94a3b8' }} axisLine={false} tickLine={false} unit="%" />
                  <Tooltip formatter={(v, name) => [`${v}%`, SENTIMENT_LABELS[name as string] ?? name]} />
                  <Legend
                    formatter={(value) => SENTIMENT_LABELS[value as string] ?? value}
                    wrapperStyle={{ fontSize: t.font.size.xs }}
                  />
                  <Bar dataKey="positive" stackId="a" fill="#22c55e" />
                  <Bar dataKey="neutral" stackId="a" fill="#94a3b8" />
                  <Bar dataKey="negative" stackId="a" fill="#ef4444" />
                  <Bar dataKey="constructive" stackId="a" fill="#3b82f6" />
                </BarChart>
              </ResponsiveContainer>
            </div>
            {/* Verdict badges per platform */}
            {report?.platform_summaries && (
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: t.space[2], marginTop: t.space[3] }}>
                {Object.entries(report.platform_summaries).map(([name, data]) => {
                  const label = (PLATFORM_SHORT_LABELS as Record<string, string>)[name] ?? name
                  const verdict = data.verdict
                  if (!verdict) return null
                  const vLower = verdict.toLowerCase()
                  const bg = vLower.includes('positive') ? '#dcfce7'
                    : vLower.includes('negative') ? '#fee2e2'
                    : vLower.includes('skepti') ? '#ffedd5'
                    : t.color.bgSubtle
                  const fg = vLower.includes('positive') ? '#15803d'
                    : vLower.includes('negative') ? t.color.dangerDark
                    : vLower.includes('skepti') ? '#c2410c'
                    : t.color.textStrong
                  return (
                    <span key={name} style={{
                      display: 'inline-flex', alignItems: 'center', gap: t.space[1],
                      fontSize: t.font.size.xs, fontWeight: t.font.weight.semibold, padding: '3px 10px',
                      borderRadius: t.radius.lg, background: bg, color: fg,
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
          <div style={{ background: t.color.bgPage, border: `1px solid ${t.color.border}`, borderRadius: t.radius.lg, padding: t.space[4], boxShadow: '0 1px 3px rgba(0,0,0,0.04)', display: 'flex', flexDirection: 'column' }}>
            <p style={{ fontSize: t.font.size.sm, fontWeight: t.font.weight.semibold, color: t.color.textMuted, textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: t.space[3] }}>
              ProductHunt Ratings
            </p>
            <div style={{ display: 'flex', alignItems: 'center', gap: t.space[4], marginBottom: t.space[3] }}>
              <span style={{ fontSize: 28, fontWeight: t.font.weight.bold, color: t.color.warning }}>
                {report?.producthunt_ratings?.avg_rating?.toFixed(1) ?? '-'}
                <span style={{ fontSize: t.font.size.lg, fontWeight: t.font.weight.normal, color: t.color.textMuted }}> / 5</span>
              </span>
              <span style={{ fontSize: t.font.size.xs, color: t.color.textMuted }}>
                {report?.producthunt_ratings?.total_reviews ?? 0} reviews
              </span>
            </div>
            <div style={{ flex: 1, minHeight: 100 }}>
              <ResponsiveContainer width="100%" height="100%">
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
                    <LabelList dataKey="count" position="right" style={{ fontSize: t.font.size.xs, fill: '#64748b' }} />
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        )}

        {/* ProductHunt Pros & Cons */}
        {phProsConsData !== null && (phProsConsData.pros.length > 0 || phProsConsData.cons.length > 0) && (
          <div style={{ background: t.color.bgPage, border: `1px solid ${t.color.border}`, borderRadius: t.radius.lg, padding: t.space[4], boxShadow: '0 1px 3px rgba(0,0,0,0.04)' }}>
            <p style={{ fontSize: t.font.size.sm, fontWeight: t.font.weight.semibold, color: t.color.textMuted, textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: t.space[3] }}>
              ProductHunt Pros &amp; Cons
            </p>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: t.space[3] }}>
              {/* Pros */}
              <div>
                <p style={{ fontSize: t.font.size.xs, fontWeight: t.font.weight.semibold, color: t.color.successAlt, marginBottom: t.space[2] }}>Pros</p>
                {phProsConsData.pros.slice(0, 5).map((item, idx) => (
                  <div key={idx} style={{ marginBottom: t.space[1] }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: t.font.size.xs, marginBottom: t.space[1] }}>
                      <span style={{ color: '#334155', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', maxWidth: '70%' }}>{item.theme}</span>
                      <span style={{ color: t.color.textSecondary, fontWeight: t.font.weight.semibold }}>{item.count}</span>
                    </div>
                    <div style={{ height: 6, background: t.color.bgSubtle, borderRadius: 3 }}>
                      <div style={{
                        height: '100%',
                        width: `${Math.min(100, (item.count / Math.max(...phProsConsData.pros.map(p => p.count), 1)) * 100)}%`,
                        background: t.color.successAlt,
                        borderRadius: 3,
                      }} />
                    </div>
                  </div>
                ))}
              </div>
              {/* Cons */}
              <div>
                <p style={{ fontSize: t.font.size.xs, fontWeight: t.font.weight.semibold, color: '#f87171', marginBottom: t.space[2] }}>Cons</p>
                {phProsConsData.cons.slice(0, 5).map((item, idx) => (
                  <div key={idx} style={{ marginBottom: t.space[1] }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: t.font.size.xs, marginBottom: t.space[1] }}>
                      <span style={{ color: '#334155', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', maxWidth: '70%' }}>{item.theme}</span>
                      <span style={{ color: t.color.textSecondary, fontWeight: t.font.weight.semibold }}>{item.count}</span>
                    </div>
                    <div style={{ height: 6, background: t.color.bgSubtle, borderRadius: 3 }}>
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
        <div style={{ background: t.color.bgPage, border: `1px solid ${t.color.border}`, borderRadius: t.radius.lg, padding: t.space[4], boxShadow: '0 1px 3px rgba(0,0,0,0.04)', marginBottom: t.space[4] }}>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: t.space[2], marginBottom: t.space[4] }}>
            <p style={{ fontSize: t.font.size.sm, fontWeight: t.font.weight.semibold, color: t.color.textMuted, textTransform: 'uppercase', letterSpacing: '0.5px', margin: 0 }}>
              Participant Profile
            </p>
            <span style={{ fontSize: t.font.size['2xl'], fontWeight: t.font.weight.bold, color: t.color.textPrimary }}>{allPersonas.length}</span>
            <span style={{ fontSize: t.font.size.sm, color: t.color.textMuted }}>total participants</span>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: t.space[4] }}>

            {/* Seniority */}
            {seniorityData.length > 0 && (
              <div style={{ display: 'flex', flexDirection: 'column', minHeight: 160 }}>
                <p style={{ fontSize: t.font.size.xs, color: t.color.textSecondary, fontWeight: t.font.weight.semibold, marginBottom: t.space[2] }}>Seniority</p>
                <div style={{ flex: 1, minHeight: 0 }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={seniorityData} layout="vertical" margin={{ top: 0, right: 8, bottom: 0, left: 0 }}>
                      <XAxis type="number" tick={{ fontSize: 11, fill: '#94a3b8' }} axisLine={false} tickLine={false} allowDecimals={false} />
                      <YAxis type="category" dataKey="name" width={72} tick={{ fontSize: 11, fill: '#64748b' }} axisLine={false} tickLine={false} />
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
                <p style={{ fontSize: t.font.size.xs, color: t.color.textSecondary, fontWeight: t.font.weight.semibold, marginBottom: t.space[2] }}>MBTI</p>
                <div style={{ flex: 1, minHeight: 0 }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={mbtiData} layout="vertical" margin={{ top: 0, right: 8, bottom: 0, left: 0 }}>
                      <XAxis type="number" tick={{ fontSize: 11, fill: '#94a3b8' }} axisLine={false} tickLine={false} allowDecimals={false} />
                      <YAxis type="category" dataKey="name" width={48} tick={{ fontSize: 11, fill: '#64748b' }} axisLine={false} tickLine={false} />
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
                <p style={{ fontSize: t.font.size.xs, color: t.color.textSecondary, fontWeight: t.font.weight.semibold, marginBottom: t.space[2] }}>Generation</p>
                <div style={{ flex: 1, minHeight: 0 }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={generationData} layout="vertical" margin={{ top: 0, right: 8, bottom: 0, left: 0 }}>
                      <XAxis type="number" tick={{ fontSize: 11, fill: '#94a3b8' }} axisLine={false} tickLine={false} allowDecimals={false} />
                      <YAxis type="category" dataKey="name" width={72} tick={{ fontSize: 11, fill: '#64748b' }} axisLine={false} tickLine={false} />
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
                <p style={{ fontSize: t.font.size.xs, color: t.color.textSecondary, fontWeight: t.font.weight.semibold, marginBottom: t.space[2] }}>Top Affiliations</p>
                <div style={{ display: 'flex', flexDirection: 'column', gap: t.space[1] }}>
                  {topAffiliations.map(a => {
                    const pct = Math.round((a.count / topAffiliations[0].count) * 100)
                    return (
                      <div key={a.name}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: t.font.size.xs, marginBottom: t.space[1] }}>
                          <span style={{ color: t.color.textStrong, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '75%' }}>{a.name}</span>
                          <span style={{ fontWeight: t.font.weight.semibold, color: t.color.textSecondary }}>{a.count}</span>
                        </div>
                        <div style={{ height: 5, borderRadius: 3, background: t.color.bgSubtle, overflow: 'hidden' }}>
                          <div style={{ height: '100%', width: `${pct}%`, background: '#8b5cf6', borderRadius: 3 }} />
                        </div>
                      </div>
                    )
                  })}
                </div>
              </div>
            )}

            {/* Average Traits */}
            {avgTraits && (
              <div>
                <p style={{ fontSize: t.font.size.xs, color: t.color.textSecondary, fontWeight: t.font.weight.semibold, marginBottom: t.space[2] }}>Avg Traits (1–10)</p>
                {[
                  { label: 'Skepticism', value: avgTraits.skepticism, color: t.color.warning },
                  { label: 'Commercial Focus', value: avgTraits.commercial_focus, color: t.color.info },
                  { label: 'Innovation', value: avgTraits.innovation_openness, color: t.color.success },
                ].map(trait => (
                  <div key={trait.label} style={{ marginBottom: t.space[2] }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: t.font.size.xs, marginBottom: t.space[1] }}>
                      <span style={{ color: t.color.textSecondary }}>{trait.label}</span>
                      <span style={{ color: t.color.textMuted }}>{trait.value.toFixed(1)}</span>
                    </div>
                    <div style={{ height: 5, borderRadius: 3, background: t.color.bgSubtle, overflow: 'hidden' }}>
                      <div style={{ height: '100%', borderRadius: 3, background: trait.color, width: `${(trait.value / 10) * 100}%` }} />
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
