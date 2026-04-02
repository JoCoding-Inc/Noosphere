import { useMemo } from 'react'
import {
  PieChart, Pie, Cell, Tooltip, ResponsiveContainer, Legend,
  BarChart, Bar, XAxis, YAxis, CartesianGrid, LabelList,
  LineChart, Line, ReferenceLine,
} from 'recharts'
import type { Platform, SocialPost, ReportJSON, Persona } from '../types'
import { PLATFORM_COLORS } from '../constants'

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

const SEGMENT_ABBREV: Record<string, string> = {
  developer: 'Dev',
  investor: 'Inv',
  skeptic: 'Skep',
  executive: 'Exec',
  founder: 'Fnd',
  pm: 'PM',
  marketer: 'Mkt',
  analyst: 'Ana',
  designer: 'Des',
  early_adopter: 'EA',
}

function formatNameWithSegment(name: string, segment?: string): string {
  if (!segment) return name
  const abbr = SEGMENT_ABBREV[segment]
  return abbr ? `${name} (${abbr})` : name
}

function getHeatColor(ratio: number): string {
  if (ratio < 0) return '#f1f5f9'
  if (ratio >= 70) return '#bbf7d0'
  if (ratio >= 50) return '#fef9c3'
  if (ratio >= 30) return '#fed7aa'
  return '#fecaca'
}

function getHeatTextColor(ratio: number): string {
  if (ratio < 0) return '#94a3b8'
  if (ratio >= 70) return '#166534'
  if (ratio >= 50) return '#854d0e'
  if (ratio >= 30) return '#9a3412'
  return '#991b1b'
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

  // Engagement alert rounds
  // Sentiment over rounds timeline
  const timelineData = useMemo(() => {
    if (!report?.sentiment_timeline) return []
    if (report.sentiment_timeline.length < 2) return []
    return report.sentiment_timeline
  }, [report])

  // Platform sentiment timeline (positive ratio per platform per round)
  const platformSentTimelineData = useMemo(() => {
    if (!report?.platform_sentiment_timeline) return { chartData: [] as Array<Record<string, number>>, platforms: [] as string[] }
    const platforms = Object.keys(report.platform_sentiment_timeline)
    if (platforms.length === 0) return { chartData: [] as Array<Record<string, number>>, platforms: [] as string[] }

    // Collect all rounds across platforms
    const roundSet = new Set<number>()
    for (const entries of Object.values(report.platform_sentiment_timeline)) {
      for (const e of entries) roundSet.add(e.round)
    }
    const rounds = Array.from(roundSet).sort((a, b) => a - b)
    if (rounds.length < 2) return { chartData: [] as Array<Record<string, number>>, platforms: [] as string[] }

    const chartData = rounds.map(round => {
      const row: Record<string, number> = { round }
      for (const platform of platforms) {
        const entry = report.platform_sentiment_timeline![platform]?.find(e => e.round === round)
        if (entry) {
          const total = entry.positive + entry.neutral + entry.negative
          row[platform] = total > 0 ? Math.round((entry.positive / total) * 100) : 0
        }
      }
      return row
    })

    return { chartData, platforms }
  }, [report])

  // ── Debate Map ─────────────────────────────────────────────────────
  const debateMapData = useMemo(() => {
    if (!report?.interaction_network || report.interaction_network.length === 0) return []
    return report.interaction_network
      .filter(e => (e.count ?? 0) >= 2)
      .sort((a, b) => (b.count ?? 0) - (a.count ?? 0))
      .slice(0, 8)
      .map(e => ({
        pair: `${formatNameWithSegment((e.from_name || e.from).split(' ')[0], e.from_segment)} \u2194 ${formatNameWithSegment((e.to_name || e.to).split(' ')[0], e.to_segment)}`,
        agree: e.agree_count ?? 0,
        disagree: e.disagree_count ?? 0,
        total: e.count ?? 0,
        pattern: e.sentiment_pattern || null,
      }))
  }, [report])

  // ── Platform × Segment Activity (stacked horizontal bar) ────────────
  const platformSegmentActivityData = useMemo(() => {
    if (!report?.platform_segments) return []
    return Object.entries(report.platform_segments).map(([platform, segments]) => {
      const row: Record<string, number | string> = {
        platform: (PLATFORM_SHORT_LABELS as Record<string, string>)[platform] ?? platform,
      }
      for (const [seg, counts] of Object.entries(segments)) {
        row[seg] = counts.total ?? 0
      }
      return row
    })
  }, [report])

  const platformSegmentActivityKeys = useMemo(() => {
    if (!report?.platform_segments) return []
    const keys = new Set<string>()
    Object.values(report.platform_segments).forEach(segs => {
      Object.keys(segs).forEach(k => keys.add(k))
    })
    return Array.from(keys)
  }, [report])

  // ── Segment Attitude Shifts ─────────────────────────────────────────
  const segmentAttitudeData = useMemo(() => {
    return (report?.segment_attitude_shifts ?? [])
      .map(s => ({
        name: s.segment,
        avg_delta: s.avg_delta,
        count: s.count,
        shifted_pct: s.count > 0 ? Math.round(s.shifted_count / s.count * 100) : 0,
      }))
      .sort((a, b) => Math.abs(b.avg_delta ?? 0) - Math.abs(a.avg_delta ?? 0))
  }, [report])

  // ── Segment Sentiment Journey (line chart) ──────────────────────────
  const segmentJourneyData = useMemo(() => {
    if (!report?.segment_journey) return { chartData: [] as Array<Record<string, number>>, segments: [] as string[] }

    const journey = report.segment_journey
    const rounds = Object.keys(journey).map(Number).sort((a, b) => a - b)
    if (rounds.length < 2) return { chartData: [] as Array<Record<string, number>>, segments: [] as string[] }

    // Aggregate total activity per segment across all rounds
    const segmentTotals: Record<string, number> = {}
    for (const round of rounds) {
      const roundData = journey[round]
      if (!roundData) continue
      for (const [seg, counts] of Object.entries(roundData)) {
        const total = counts.positive + counts.negative + counts.neutral + counts.constructive
        segmentTotals[seg] = (segmentTotals[seg] ?? 0) + total
      }
    }

    // Pick top 3 segments by total activity
    const topSegments = Object.entries(segmentTotals)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 3)
      .map(([seg]) => seg)

    if (topSegments.length === 0) return { chartData: [] as Array<Record<string, number>>, segments: [] as string[] }

    const chartData = rounds.map(round => {
      const row: Record<string, number> = { round }
      const roundData = journey[round]
      if (!roundData) return row
      for (const seg of topSegments) {
        const counts = roundData[seg]
        if (counts) {
          const total = counts.positive + counts.negative + counts.neutral + counts.constructive
          row[seg] = total > 0 ? Math.round(counts.positive / total * 100) : 0
        }
      }
      return row
    })

    return { chartData, segments: topSegments }
  }, [report])

  // ── Segment Attitude Heatmap ─────────────────────────────────────────
  const segmentHeatmapData = useMemo(() => {
    if (!report?.segment_journey) return null
    const rounds = Object.keys(report.segment_journey).map(Number).sort((a, b) => a - b)
    const segments = new Set<string>()
    rounds.forEach(r => {
      Object.keys(report.segment_journey![r] || {}).forEach(s => segments.add(s))
    })
    const segList = Array.from(segments)
    if (rounds.length < 2 || segList.length < 2) return null

    const matrix: Record<string, Record<number, number>> = {}
    segList.forEach(seg => {
      matrix[seg] = {}
      rounds.forEach(r => {
        const counts = report.segment_journey![r]?.[seg]
        if (!counts) { matrix[seg][r] = -1; return }
        const total = (counts.positive || 0) + (counts.negative || 0) + (counts.neutral || 0) + (counts.constructive || 0)
        if (total === 0) { matrix[seg][r] = -1; return }
        matrix[seg][r] = Math.round(((counts.positive || 0) + (counts.constructive || 0) * 0.5) / total * 100)
      })
    })
    return { rounds, segments: segList, matrix }
  }, [report])

  // ── Archetype Narratives ──────────────────────────────────────────────
  const archetypeNarrativeItems = useMemo(() => {
    if (!report?.archetype_narratives?.length) return []
    return report.archetype_narratives
      .filter(n => n.journey_summary)
      .slice(0, 5)
  }, [report])

  // ── Unaddressed Concerns ──────────────────────────────────────────────
  const unaddressedConcernsData = useMemo(() => {
    if (!report?.unaddressed_concerns) return []
    return [...report.unaddressed_concerns]
      .sort((a, b) => (b.weighted_score || 0) - (a.weighted_score || 0))
      .slice(0, 5)
  }, [report])

  // ── Q&A Analysis ───────────────────────────────────────────────────
  const qaAnalysisData = useMemo(() => {
    if (!report?.qa_pairs?.length) return null
    const byPlatform: Record<string, { answered: number; unanswered: number }> = {}
    for (const qa of report.qa_pairs) {
      if (!byPlatform[qa.platform]) byPlatform[qa.platform] = { answered: 0, unanswered: 0 }
      if (qa.answered) byPlatform[qa.platform].answered++
      else byPlatform[qa.platform].unanswered++
    }
    const platformData = Object.entries(byPlatform).map(([platform, v]) => ({
      name: (PLATFORM_SHORT_LABELS as Record<string, string>)[platform] ?? platform,
      ...v,
    }))
    const unanswered = report.qa_pairs
      .filter(q => !q.answered)
      .slice(0, 3)
    return { platformData, unanswered, responseRate: report.qa_response_rate ?? null }
  }, [report])

  // ── Platform Segments with constructive ─────────────────────────────
  const platformSegmentsData = useMemo(() => {
    if (!report?.platform_segments) return []
    const result: Array<{ platform: string; segment: string; positive: number; neutral: number; negative: number; constructive_pct: number; effective_positive_pct: number; total: number }> = []
    for (const [platform, segments] of Object.entries(report.platform_segments)) {
      const platLabel = (PLATFORM_SHORT_LABELS as Record<string, string>)[platform] ?? platform
      for (const [segment, data] of Object.entries(segments)) {
        if (data.total === 0) continue
        result.push({
          platform: platLabel,
          segment,
          positive: data.positive_pct ?? (data.total > 0 ? Math.round(data.positive / data.total * 100) : 0),
          neutral: data.total > 0 ? Math.round(data.neutral / data.total * 100) : 0,
          negative: data.negative_pct ?? (data.total > 0 ? Math.round(data.negative / data.total * 100) : 0),
          constructive_pct: data.constructive_pct ?? 0,
          effective_positive_pct: data.effective_positive_pct ?? 0,
          total: data.total,
        })
      }
    }
    return result
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

  // ── Influence Flow ────────────────────────────────────────────────
  const influenceFlowData = useMemo(() => {
    if (!report?.influence_flow || report.influence_flow.length === 0) return []
    return [...report.influence_flow]
      .sort((a, b) => Math.abs(b.delta ?? 0) - Math.abs(a.delta ?? 0))
      .slice(0, 10)
      .map((item, idx) => ({
        id: idx,
        influencer: item.influencer_name,
        influenced: item.influenced_name,
        round: item.round,
        delta: item.delta ?? 0,
        snippet: item.trigger_snippet,
        influencerSegment: item.influencer_segment,
        influencedSegment: item.influenced_segment,
        positive: item.delta > 0 ? item.delta : 0,
        negative: item.delta < 0 ? Math.abs(item.delta) : 0,
      }))
  }, [report])

  const influenceBySegmentData = useMemo(() => {
    if (!report?.influence_flow || report.influence_flow.length === 0) return []
    const givenMap = new Map<string, number>()
    const receivedMap = new Map<string, number>()
    for (const item of report.influence_flow) {
      const seg1 = item.influencer_segment || 'other'
      const seg2 = item.influenced_segment || 'other'
      givenMap.set(seg1, (givenMap.get(seg1) ?? 0) + (item.delta ?? 0))
      receivedMap.set(seg2, (receivedMap.get(seg2) ?? 0) + (item.delta ?? 0))
    }
    const allSegs = new Set([...givenMap.keys(), ...receivedMap.keys()])
    return Array.from(allSegs)
      .map(seg => ({
        segment: seg,
        label: SEGMENT_LABELS[seg] ?? seg,
        given: +(givenMap.get(seg) ?? 0).toFixed(2),
        received: +(receivedMap.get(seg) ?? 0).toFixed(2),
      }))
      .sort((a, b) => Math.abs(b.given) + Math.abs(b.received) - Math.abs(a.given) - Math.abs(a.received))
      .slice(0, 6)
  }, [report])

  const envInfluenceData = useMemo(() => {
    const ei = report?.environmental_influence
    if (!ei) return null
    return [
      { label: 'Passive Exposure', count: ei.passive_exposure_count, delta: ei.passive_exposure_total_delta ?? 0 },
      { label: 'Late Joiner Conformity', count: ei.late_joiner_count, delta: ei.late_joiner_total_delta ?? 0 },
      { label: 'Cross-Platform Sync', count: ei.cross_sync_count, delta: ei.cross_sync_total_delta ?? 0 },
    ].filter(d => d.count > 0)
  }, [report])

  const conversionFunnelData = useMemo(() => {
    if (!report?.segment_conversion_funnel) return []
    return Object.entries(report.segment_conversion_funnel)
      .map(([seg, d]) => {
        const label = SEGMENT_LABELS[seg] ?? seg
        return {
          segment: label.length > 12 ? label.slice(0, 12) + '\u2026' : label,
          fullSegment: label,
          conversion_rate: Math.round((d.conversion_rate ?? 0) * 100),
          resistance_rate: Math.round((d.resistance_rate ?? 0) * 100),
          avg_rounds: d.avg_rounds_to_convert,
          total: d.total,
        }
      })
      .filter(d => d.total > 0)
      .sort((a, b) => b.conversion_rate - a.conversion_rate)
      .slice(0, 8)
  }, [report])

  const debateTimelineItems = useMemo(() => {
    if (!report?.debate_timeline?.length) return []
    return [...report.debate_timeline]
      .sort((a, b) => b.total_replies - a.total_replies)
      .slice(0, 3)
  }, [report])

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

  const hasData = sentimentData.length > 0 || criticismData.length > 0 || platformDepthData.length > 0
    || praiseData.length > 0 || platformReceptionData.length > 0 || timelineData.length > 0
    || platformSentTimelineData.chartData.length > 0 || hasPersonaData
    || segmentAttitudeData.length > 0
    || platformSegmentsData.length > 0 || segmentJourneyData.chartData.length > 0
    || platformSegmentActivityData.length > 0 || influenceFlowData.length > 0
    || conversionFunnelData.length > 0
    || archetypeNarrativeItems.length > 0
    || unaddressedConcernsData.length > 0
    || qaAnalysisData !== null
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

        {/* Sentiment Over Rounds (line chart) */}
        {timelineData.length > 0 && (
          <div style={{ background: '#fff', border: '1px solid #e2e8f0', borderRadius: 10, padding: 16, boxShadow: '0 1px 3px rgba(0,0,0,0.04)' }}>
            <p style={{ fontSize: 12, fontWeight: 600, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 12 }}>
              Sentiment Over Rounds
            </p>
            <ResponsiveContainer width="100%" height={200}>
              <LineChart data={timelineData} margin={{ top: 0, right: 8, bottom: 0, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                <XAxis dataKey="round" tick={{ fontSize: 11, fill: '#64748b' }} axisLine={false} tickLine={false} label={{ value: 'Round', position: 'insideBottomRight', offset: -5, style: { fontSize: 10, fill: '#94a3b8' } }} />
                <YAxis tick={{ fontSize: 11, fill: '#94a3b8' }} axisLine={false} tickLine={false} allowDecimals={false} />
                <Tooltip formatter={(v, name) => [v, SENTIMENT_LABELS[name as string] ?? name]} />
                <Legend
                  formatter={(value) => SENTIMENT_LABELS[value as string] ?? value}
                  wrapperStyle={{ fontSize: 11 }}
                />
                <Line type="monotone" dataKey="positive" stroke="#22c55e" strokeWidth={2} dot={{ r: 3 }} />
                <Line type="monotone" dataKey="neutral" stroke="#94a3b8" strokeWidth={2} dot={{ r: 3 }} />
                <Line type="monotone" dataKey="negative" stroke="#ef4444" strokeWidth={2} dot={{ r: 3 }} />
                <Line type="monotone" dataKey="engagement" stroke="#f59e0b" strokeWidth={2} dot={{ r: 3 }} />
                <Line type="monotone" dataKey="constructive" stroke="#06b6d4" strokeWidth={2} dot={{ r: 3 }} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}

        {/* Segment Sentiment Journey (line chart) */}
        {segmentJourneyData.chartData.length > 0 && (
          <div style={{ background: '#fff', border: '1px solid #e2e8f0', borderRadius: 10, padding: 16, boxShadow: '0 1px 3px rgba(0,0,0,0.04)' }}>
            <p style={{ fontSize: 12, fontWeight: 600, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 12 }}>
              Segment Sentiment Journey
            </p>
            <p style={{ fontSize: 11, color: '#cbd5e1', marginBottom: 10 }}>Positive sentiment % per segment over rounds</p>
            <ResponsiveContainer width="100%" height={200}>
              <LineChart data={segmentJourneyData.chartData} margin={{ top: 0, right: 8, bottom: 0, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                <XAxis dataKey="round" tick={{ fontSize: 11, fill: '#64748b' }} axisLine={false} tickLine={false} label={{ value: 'Round', position: 'insideBottomRight', offset: -5, style: { fontSize: 10, fill: '#94a3b8' } }} />
                <YAxis tick={{ fontSize: 11, fill: '#94a3b8' }} axisLine={false} tickLine={false} unit="%" domain={[0, 100]} />
                <Tooltip formatter={(v, name) => [`${v}%`, SEGMENT_LABELS[name as string] ?? name]} />
                <Legend
                  formatter={(value) => SEGMENT_LABELS[value as string] ?? value}
                  wrapperStyle={{ fontSize: 11 }}
                />
                {segmentJourneyData.segments.map(seg => (
                  <Line
                    key={seg}
                    type="monotone"
                    dataKey={seg}
                    stroke={SEGMENT_COLORS[seg] ?? '#64748b'}
                    strokeWidth={2}
                    dot={{ r: 3 }}
                  />
                ))}
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}

        {/* Platform Sentiment Over Time (positive ratio per platform) */}
        {platformSentTimelineData.chartData.length > 0 && (
          <div style={{ background: '#fff', border: '1px solid #e2e8f0', borderRadius: 10, padding: 16, boxShadow: '0 1px 3px rgba(0,0,0,0.04)' }}>
            <p style={{ fontSize: 12, fontWeight: 600, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 12 }}>
              Platform Sentiment Over Time
            </p>
            <p style={{ fontSize: 11, color: '#cbd5e1', marginBottom: 10 }}>Positive sentiment % per platform over rounds</p>
            <ResponsiveContainer width="100%" height={200}>
              <LineChart data={platformSentTimelineData.chartData} margin={{ top: 0, right: 8, bottom: 0, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                <XAxis dataKey="round" tick={{ fontSize: 11, fill: '#64748b' }} axisLine={false} tickLine={false} label={{ value: 'Round', position: 'insideBottomRight', offset: -5, style: { fontSize: 10, fill: '#94a3b8' } }} />
                <YAxis tick={{ fontSize: 11, fill: '#94a3b8' }} axisLine={false} tickLine={false} unit="%" domain={[0, 100]} />
                <Tooltip formatter={(v, name) => [`${v}%`, (PLATFORM_SHORT_LABELS as Record<string, string>)[name as string] ?? name]} />
                <Legend
                  formatter={(value) => (PLATFORM_SHORT_LABELS as Record<string, string>)[value] ?? value}
                  wrapperStyle={{ fontSize: 11 }}
                />
                {platformSentTimelineData.platforms.map(platform => (
                  <Line
                    key={platform}
                    type="monotone"
                    dataKey={platform}
                    stroke={PLATFORM_COLORS[platform as Platform] ?? '#64748b'}
                    strokeWidth={2}
                    dot={{ r: 3 }}
                  />
                ))}
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}

        {/* Segment Attitude Shifts */}
        {segmentAttitudeData.length > 0 && (
          <div style={{ background: '#fff', border: '1px solid #e2e8f0', borderRadius: 10, padding: 16, boxShadow: '0 1px 3px rgba(0,0,0,0.04)' }}>
            <p style={{ fontSize: 12, fontWeight: 600, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 12 }}>
              Segment Attitude Shifts
            </p>
            <ResponsiveContainer width="100%" height={Math.max(120, segmentAttitudeData.length * 36)}>
              <BarChart data={segmentAttitudeData} layout="vertical" margin={{ top: 0, right: 8, bottom: 0, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" horizontal={false} />
                <XAxis type="number" tick={{ fontSize: 11, fill: '#94a3b8' }} axisLine={false} tickLine={false} />
                <YAxis
                  type="category"
                  dataKey="name"
                  width={120}
                  tick={{ fontSize: 11, fill: '#64748b' }}
                  axisLine={false}
                  tickLine={false}
                />
                <Tooltip
                  cursor={{ fill: '#f8fafc' }}
                  // eslint-disable-next-line @typescript-eslint/no-explicit-any
                  formatter={(_v: any, _name: any, props: any) => {
                    const d = props?.payload
                    if (!d) return [String(_v), 'Attitude Shift']
                    return [`${(d.avg_delta ?? 0) > 0 ? '+' : ''}${(d.avg_delta ?? 0).toFixed(2)} avg delta (${d.shifted_pct}% shifted, n=${d.count})`, 'Attitude Shift']
                  }}
                />
                <Bar dataKey="avg_delta" radius={[0, 3, 3, 0]}>
                  {segmentAttitudeData.map((entry, idx) => (
                    <Cell key={idx} fill={(entry.avg_delta ?? 0) >= 0 ? '#10b981' : '#ef4444'} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}

        {/* Archetype Narratives */}
        {archetypeNarrativeItems.length > 0 && (
          <div style={{ background: '#fff', border: '1px solid #e2e8f0', borderRadius: 10, padding: 16, boxShadow: '0 1px 3px rgba(0,0,0,0.04)' }}>
            <p style={{ fontSize: 12, fontWeight: 600, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 12 }}>
              Archetype Narratives
            </p>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              {archetypeNarrativeItems.map((n, i) => (
                <div key={i} style={{
                  border: '1px solid #e2e8f0', borderRadius: 8, padding: 14, background: '#fff'
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                    <span style={{ fontSize: 12, fontWeight: 600, color: '#1e293b' }}>{n.segment}</span>
                    <span style={{
                      fontSize: 10, padding: '1px 7px', borderRadius: 8, fontWeight: 600,
                      background: (n.attitude_delta ?? 0) >= 0.1 ? '#dcfce7' : (n.attitude_delta ?? 0) <= -0.1 ? '#fee2e2' : '#f1f5f9',
                      color: (n.attitude_delta ?? 0) >= 0.1 ? '#15803d' : (n.attitude_delta ?? 0) <= -0.1 ? '#b91c1c' : '#475569',
                    }}>
                      {(n.attitude_delta ?? 0) >= 0 ? '+' : ''}{(n.attitude_delta ?? 0).toFixed(2)}
                    </span>
                    <span style={{ fontSize: 10, color: '#94a3b8', marginLeft: 'auto' }}>
                      {n.persona_count} personas
                    </span>
                  </div>
                  {n.platform_breakdown && Object.keys(n.platform_breakdown).length > 0 && (
                    <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 6 }}>
                      {Object.entries(n.platform_breakdown).map(([plat, delta]) => (
                        <span key={plat} style={{
                          fontSize: 10, fontWeight: 600,
                          color: (delta ?? 0) > 0 ? '#22c55e' : (delta ?? 0) < 0 ? '#ef4444' : '#94a3b8',
                        }}>
                          {(PLATFORM_SHORT_LABELS as Record<string, string>)[plat] ?? plat}: {(delta ?? 0) > 0 ? '+' : ''}{(delta ?? 0).toFixed(2)}
                        </span>
                      ))}
                    </div>
                  )}
                  <p style={{ fontSize: 12, color: '#475569', lineHeight: 1.6, margin: '0 0 8px' }}>
                    {n.journey_summary}
                  </p>
                  {(n.pivot_rounds?.length ?? 0) > 0 && (
                    <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                      {(n.pivot_rounds ?? []).map((pr, pi) => (
                        <span key={pi} style={{
                          fontSize: 10, padding: '1px 6px', borderRadius: 6, fontWeight: 600,
                          background: pr.direction === 'positive' ? '#dcfce7' : '#fee2e2',
                          color: pr.direction === 'positive' ? '#15803d' : '#b91c1c',
                        }}>
                          R{pr.round} {pr.direction === 'positive' ? '\u25B2' : '\u25BC'} {(pr.delta_pct ?? 0) > 0 ? '+' : ''}{(pr.delta_pct ?? 0).toFixed(0)}%
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Unaddressed Concerns */}
        {unaddressedConcernsData.length > 0 && (
          <div style={{ background: '#fff', border: '1px solid #e2e8f0', borderRadius: 10, padding: 16, boxShadow: '0 1px 3px rgba(0,0,0,0.04)' }}>
            <p style={{ fontSize: 12, fontWeight: 600, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 12 }}>
              Unaddressed Concerns
            </p>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {unaddressedConcernsData.map((c, i) => {
                const sentimentDotColor =
                  c.sentiment === 'positive' ? '#22c55e'
                  : c.sentiment === 'negative' ? '#ef4444'
                  : c.sentiment === 'constructive' ? '#3b82f6'
                  : '#94a3b8'
                const platformLabel = (PLATFORM_SHORT_LABELS as Record<string, string>)[c.platform] ?? c.platform
                return (
                  <div key={c.post_id || i} style={{
                    border: '1px solid #e2e8f0', borderRadius: 8, padding: '10px 12px', background: '#f8fafc',
                  }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6, flexWrap: 'wrap' }}>
                      <span style={{
                        fontSize: 10, fontWeight: 600, padding: '1px 6px', borderRadius: 6,
                        background: PLATFORM_COLORS[c.platform as Platform] ?? '#6b7280',
                        color: '#fff',
                      }}>
                        {platformLabel}
                      </span>
                      <span style={{ fontSize: 11, fontWeight: 600, color: '#334155' }}>
                        {c.author_name}{c.author_segment ? ` (${SEGMENT_ABBREV[c.author_segment] || c.author_segment})` : ''}
                      </span>
                      <span style={{
                        display: 'inline-block', width: 8, height: 8, borderRadius: '50%',
                        background: sentimentDotColor, flexShrink: 0,
                      }} title={c.sentiment} />
                      <span style={{ fontSize: 10, color: '#94a3b8', marginLeft: 'auto', fontWeight: 600 }}>
                        {(c.weighted_score ?? 0).toFixed(2)}
                      </span>
                    </div>
                    <p style={{ fontSize: 12, color: '#475569', lineHeight: 1.5, margin: 0 }}>
                      {c.content_snippet}
                    </p>
                  </div>
                )
              })}
            </div>
          </div>
        )}

        {/* Q&A Analysis */}
        {qaAnalysisData !== null && (
          <div style={{ background: '#fff', border: '1px solid #e2e8f0', borderRadius: 10, padding: 16, boxShadow: '0 1px 3px rgba(0,0,0,0.04)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 12 }}>
              <p style={{ fontSize: 12, fontWeight: 600, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.5px', margin: 0 }}>
                Q&A Analysis
              </p>
              {qaAnalysisData.responseRate !== null && (
                <span style={{
                  fontSize: 20, fontWeight: 700,
                  color: qaAnalysisData.responseRate >= 0.7 ? '#22c55e' : qaAnalysisData.responseRate >= 0.4 ? '#f59e0b' : '#ef4444',
                }}>
                  {(qaAnalysisData.responseRate * 100).toFixed(0)}%
                  <span style={{ fontSize: 11, fontWeight: 500, color: '#94a3b8', marginLeft: 4 }}>response rate</span>
                </span>
              )}
            </div>

            {qaAnalysisData.platformData.length > 0 && (
              <ResponsiveContainer width="100%" height={Math.max(100, qaAnalysisData.platformData.length * 36)}>
                <BarChart data={qaAnalysisData.platformData} layout="vertical" margin={{ top: 0, right: 8, bottom: 0, left: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" horizontal={false} />
                  <XAxis type="number" tick={{ fontSize: 11, fill: '#94a3b8' }} axisLine={false} tickLine={false} allowDecimals={false} />
                  <YAxis type="category" dataKey="name" width={60} tick={{ fontSize: 11, fill: '#64748b' }} axisLine={false} tickLine={false} />
                  <Tooltip cursor={{ fill: '#f8fafc' }} />
                  <Bar dataKey="answered" stackId="qa" fill="#10b981" radius={[0, 0, 0, 0]} name="Answered" />
                  <Bar dataKey="unanswered" stackId="qa" fill="#f87171" radius={[0, 3, 3, 0]} name="Unanswered" />
                </BarChart>
              </ResponsiveContainer>
            )}

            {qaAnalysisData.unanswered.length > 0 && (
              <div style={{ marginTop: 14 }}>
                <p style={{ fontSize: 11, fontWeight: 600, color: '#64748b', marginBottom: 8 }}>Unanswered Questions</p>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                  {qaAnalysisData.unanswered.map((qa, i) => {
                    const platLabel = (PLATFORM_SHORT_LABELS as Record<string, string>)[qa.platform] ?? qa.platform
                    return (
                      <div key={qa.question_id || i} style={{
                        border: '1px solid #e2e8f0', borderRadius: 8, padding: '8px 10px', background: '#fef2f2',
                      }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
                          <span style={{
                            fontSize: 10, fontWeight: 600, padding: '1px 6px', borderRadius: 6,
                            background: PLATFORM_COLORS[qa.platform as Platform] ?? '#6b7280',
                            color: '#fff',
                          }}>
                            {platLabel}
                          </span>
                          <span style={{ fontSize: 11, fontWeight: 600, color: '#334155' }}>{qa.author_name}</span>
                        </div>
                        <p style={{ fontSize: 12, color: '#475569', lineHeight: 1.4, margin: 0 }}>
                          {qa.question_text.length > 100 ? `${qa.question_text.slice(0, 100)}...` : qa.question_text}
                        </p>
                      </div>
                    )
                  })}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Segment Attitude Heatmap */}
        {segmentHeatmapData && (
          <div style={{ background: '#fff', border: '1px solid #e2e8f0', borderRadius: 10, padding: 16, boxShadow: '0 1px 3px rgba(0,0,0,0.04)', gridColumn: '1 / -1' }}>
            <p style={{ fontSize: 12, fontWeight: 600, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 12 }}>
              Segment Attitude Heatmap (Positive Ratio %)
            </p>
            <div style={{ overflowX: 'auto' }}>
              <div style={{
                display: 'grid',
                gridTemplateColumns: `120px repeat(${segmentHeatmapData.rounds.length}, minmax(40px, 1fr))`,
                gap: 2,
                minWidth: segmentHeatmapData.rounds.length > 10 ? segmentHeatmapData.rounds.length * 48 + 120 : undefined,
              }}>
                {/* Header row */}
                <div style={{ fontSize: 11, fontWeight: 600, color: '#64748b', padding: '4px 6px' }} />
                {segmentHeatmapData.rounds.map(r => (
                  <div key={r} style={{ fontSize: 11, fontWeight: 600, color: '#64748b', padding: '4px 2px', textAlign: 'center' }}>
                    R{r}
                  </div>
                ))}
                {/* Data rows */}
                {segmentHeatmapData.segments.map(seg => (
                  <div key={seg} style={{ display: 'contents' }}>
                    <div style={{ fontSize: 11, fontWeight: 500, color: '#334155', padding: '6px 6px', display: 'flex', alignItems: 'center', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                      {SEGMENT_LABELS[seg] ?? seg}
                    </div>
                    {segmentHeatmapData.rounds.map(r => {
                      const ratio = segmentHeatmapData.matrix[seg][r]
                      const counts = report?.segment_journey?.[r]?.[seg]
                      const tooltipText = ratio < 0
                        ? 'No data'
                        : `${SEGMENT_LABELS[seg] ?? seg} R${r}: ${ratio}% positive ratio\nP:${counts?.positive ?? 0} N:${counts?.negative ?? 0} Neu:${counts?.neutral ?? 0} C:${counts?.constructive ?? 0}`
                      return (
                        <div
                          key={r}
                          title={tooltipText}
                          style={{
                            background: getHeatColor(ratio),
                            color: getHeatTextColor(ratio),
                            fontSize: 11,
                            fontWeight: 600,
                            padding: '6px 2px',
                            textAlign: 'center',
                            borderRadius: 4,
                            cursor: 'default',
                            transition: 'opacity 0.15s',
                          }}
                        >
                          {ratio < 0 ? '-' : ratio}
                        </div>
                      )
                    })}
                  </div>
                ))}
              </div>
            </div>
            {/* Legend */}
            <div style={{ display: 'flex', gap: 12, marginTop: 10, fontSize: 10, color: '#64748b', alignItems: 'center' }}>
              <span style={{ fontWeight: 600 }}>Legend:</span>
              {[
                { color: '#bbf7d0', label: '70%+' },
                { color: '#fef9c3', label: '50-69%' },
                { color: '#fed7aa', label: '30-49%' },
                { color: '#fecaca', label: '<30%' },
                { color: '#f1f5f9', label: 'No data' },
              ].map(item => (
                <span key={item.label} style={{ display: 'inline-flex', alignItems: 'center', gap: 3 }}>
                  <span style={{ width: 10, height: 10, borderRadius: 2, background: item.color, display: 'inline-block', border: '1px solid #e2e8f0' }} />
                  {item.label}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Segment Conversion Funnel */}
        {conversionFunnelData.length > 0 && (
          <div style={{ background: '#fff', border: '1px solid #e2e8f0', borderRadius: 10, padding: 16, boxShadow: '0 1px 3px rgba(0,0,0,0.04)', gridColumn: '1 / -1' }}>
            <h3 style={{ fontSize: 14, fontWeight: 600, color: '#1e293b', marginBottom: 4 }}>
              Segment Conversion Funnel
            </h3>
            <p style={{ fontSize: 11, color: '#94a3b8', marginBottom: 12 }}>
              Conversion vs resistance rate by segment
            </p>
            <ResponsiveContainer width="100%" height={Math.max(180, conversionFunnelData.length * 36)}>
              <BarChart
                data={conversionFunnelData}
                layout="vertical"
                margin={{ top: 4, right: 40, left: 8, bottom: 4 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" horizontal={false} />
                <XAxis type="number" domain={[0, 100]} tick={{ fontSize: 10 }} unit="%" />
                <YAxis type="category" dataKey="segment" tick={{ fontSize: 10 }} width={90} />
                <Tooltip
                  content={({ active, payload, label }: any) => {
                    if (!active || !payload?.length) return null
                    const d = payload[0]?.payload
                    return (
                      <div style={{ background: '#fff', border: '1px solid #e2e8f0', borderRadius: 6, padding: '8px 10px', fontSize: 11, boxShadow: '0 2px 6px rgba(0,0,0,0.08)' }}>
                        <div style={{ fontWeight: 600, color: '#1e293b', marginBottom: 4 }}>{d?.fullSegment ?? label}</div>
                        {payload.map((p: any) => (
                          <div key={p.dataKey} style={{ color: p.fill, marginBottom: 2 }}>
                            {p.name}: {p.value}%
                          </div>
                        ))}
                        {d?.avg_rounds != null && (
                          <div style={{ color: '#64748b', marginTop: 4, borderTop: '1px solid #f1f5f9', paddingTop: 4 }}>
                            Avg {d.avg_rounds} rounds to convert
                          </div>
                        )}
                      </div>
                    )
                  }}
                />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                <Bar dataKey="conversion_rate" name="Converted" fill="#22c55e" radius={[0, 3, 3, 0]}>
                  <LabelList
                    dataKey="avg_rounds"
                    position="right"
                    style={{ fontSize: 10, fill: '#64748b' }}
                    formatter={(v: unknown) => (v != null && v !== '') ? `~${v}R` : ''}
                  />
                </Bar>
                <Bar dataKey="resistance_rate" name="Resistant" fill="#ef4444" radius={[0, 3, 3, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}

        {/* Debate Map (stacked horizontal bar chart) */}
        {debateMapData.length > 0 && (
          <div style={{ background: '#fff', border: '1px solid #e2e8f0', borderRadius: 10, padding: 16, boxShadow: '0 1px 3px rgba(0,0,0,0.04)' }}>
            <p style={{ fontSize: 12, fontWeight: 600, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 12 }}>
              Debate Map
            </p>
            <ResponsiveContainer width="100%" height={Math.max(120, debateMapData.length * 36)}>
              <BarChart data={debateMapData} layout="vertical" margin={{ top: 0, right: 8, bottom: 0, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" horizontal={false} />
                <XAxis type="number" tick={{ fontSize: 11, fill: '#94a3b8' }} axisLine={false} tickLine={false} />
                <YAxis
                  type="category"
                  dataKey="pair"
                  width={120}
                  tick={{ fontSize: 11, fill: '#64748b' }}
                  axisLine={false}
                  tickLine={false}
                />
                <Tooltip
                  cursor={{ fill: '#f0fdf4' }}
                  content={({ active, payload, label }) => {
                    if (!active || !payload || payload.length === 0) return null
                    const item = debateMapData.find(d => d.pair === label)
                    const patternStyle: Record<string, { label: string; color: string; bg: string }> = {
                      debate: { label: 'Debate', color: '#dc2626', bg: '#fef2f2' },
                      aligned: { label: 'Aligned', color: '#16a34a', bg: '#f0fdf4' },
                      mixed: { label: 'Mixed', color: '#ca8a04', bg: '#fefce8' },
                    }
                    const ps = item?.pattern ? patternStyle[item.pattern] : null
                    return (
                      <div style={{ background: '#fff', border: '1px solid #e2e8f0', borderRadius: 6, padding: '8px 12px', fontSize: 11, boxShadow: '0 2px 8px rgba(0,0,0,0.08)' }}>
                        <p style={{ fontWeight: 600, color: '#334155', marginBottom: 4 }}>{label}</p>
                        {payload.map((p, i) => (
                          <p key={i} style={{ color: String(p.color || '#64748b'), margin: '2px 0' }}>{String(p.name ?? '')}: {String(p.value ?? '')}</p>
                        ))}
                        {ps && (
                          <span style={{ display: 'inline-block', marginTop: 4, padding: '1px 6px', borderRadius: 4, fontSize: 10, fontWeight: 600, color: ps.color, background: ps.bg }}>
                            {ps.label}
                          </span>
                        )}
                      </div>
                    )
                  }}
                />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                <Bar dataKey="agree" stackId="a" fill="#22c55e" name="Agree" radius={[0, 0, 0, 0]} />
                <Bar dataKey="disagree" stackId="a" fill="#ef4444" name="Disagree" radius={[0, 3, 3, 0]} />
              </BarChart>
            </ResponsiveContainer>
            {/* Pattern badges below chart */}
            {debateMapData.some(d => d.pattern) && (
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 8 }}>
                {debateMapData.filter(d => d.pattern && d.pattern !== 'neutral').map((d, idx) => {
                  const styles: Record<string, { color: string; bg: string }> = {
                    debate: { color: '#dc2626', bg: '#fef2f2' },
                    aligned: { color: '#16a34a', bg: '#f0fdf4' },
                    mixed: { color: '#ca8a04', bg: '#fefce8' },
                  }
                  const s = styles[d.pattern!] || { color: '#64748b', bg: '#f1f5f9' }
                  return (
                    <span key={idx} style={{ display: 'inline-flex', alignItems: 'center', gap: 4, padding: '2px 8px', borderRadius: 4, fontSize: 10, fontWeight: 600, color: s.color, background: s.bg }}>
                      {d.pattern === 'debate' ? 'Debate' : d.pattern === 'aligned' ? 'Aligned' : 'Mixed'}
                      <span style={{ fontWeight: 400, color: '#64748b' }}>{d.pair.length > 20 ? d.pair.slice(0, 20) + '...' : d.pair}</span>
                    </span>
                  )
                })}
              </div>
            )}
          </div>
        )}

        {/* Platform × Segment Activity (stacked horizontal bar) */}
        {platformSegmentActivityData.length > 0 && platformSegmentActivityKeys.length > 0 && (
          <div style={{ background: '#fff', border: '1px solid #e2e8f0', borderRadius: 10, padding: 16, boxShadow: '0 1px 3px rgba(0,0,0,0.04)' }}>
            <p style={{ fontSize: 12, fontWeight: 600, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 12 }}>
              Platform &times; Segment Activity
            </p>
            <ResponsiveContainer width="100%" height={Math.max(140, platformSegmentActivityData.length * 44)}>
              <BarChart data={platformSegmentActivityData} layout="vertical" margin={{ top: 0, right: 8, bottom: 0, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" horizontal={false} />
                <XAxis type="number" tick={{ fontSize: 11, fill: '#94a3b8' }} axisLine={false} tickLine={false} />
                <YAxis
                  type="category"
                  dataKey="platform"
                  width={110}
                  tick={{ fontSize: 11, fill: '#64748b' }}
                  axisLine={false}
                  tickLine={false}
                />
                <Tooltip cursor={{ fill: '#f8fafc' }} formatter={(value: unknown, name: unknown) => [value as number, SEGMENT_LABELS[name as string] ?? (name as string)]} />
                <Legend wrapperStyle={{ fontSize: 11 }} formatter={(value: string) => SEGMENT_LABELS[value] ?? value} />
                {platformSegmentActivityKeys.map((seg, idx) => {
                  const palette = ['#6366f1', '#f59e0b', '#10b981', '#ef4444', '#8b5cf6', '#06b6d4', '#f43f5e', '#a78bfa']
                  const color = SEGMENT_COLORS[seg] ?? palette[idx % palette.length]
                  const isLast = idx === platformSegmentActivityKeys.length - 1
                  return (
                    <Bar
                      key={seg}
                      dataKey={seg}
                      stackId="a"
                      fill={color}
                      name={seg}
                      radius={isLast ? [0, 3, 3, 0] : [0, 0, 0, 0]}
                    />
                  )
                })}
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}

        {/* Influence Flow (card list + segment bar chart) */}
        {influenceFlowData.length > 0 && (
          <div style={{ background: '#fff', border: '1px solid #e2e8f0', borderRadius: 10, padding: 16, boxShadow: '0 1px 3px rgba(0,0,0,0.04)' }}>
            <p style={{ fontSize: 12, fontWeight: 600, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 12 }}>
              Influence Flow
            </p>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {influenceFlowData.map(item => (
                <div
                  key={item.id}
                  style={{
                    display: 'flex', alignItems: 'flex-start', gap: 10,
                    padding: '10px 12px', borderRadius: 8,
                    background: '#f8fafc', border: '1px solid #e2e8f0',
                  }}
                >
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
                      <span style={{ fontWeight: 600, fontSize: 13, color: '#1e293b' }}>{item.influencer}</span>
                      <span style={{ color: item.delta > 0 ? '#22c55e' : '#ef4444', fontWeight: 700, fontSize: 14 }}>
                        {item.delta > 0 ? '\u2192' : '\u2192'}
                      </span>
                      <span style={{ fontWeight: 600, fontSize: 13, color: '#1e293b' }}>{item.influenced}</span>
                      <span style={{ fontSize: 11, color: '#94a3b8', marginLeft: 4 }}>R{item.round}</span>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 4, flexWrap: 'wrap' }}>
                      <span style={{
                        display: 'inline-block', fontSize: 10, fontWeight: 600,
                        padding: '1px 6px', borderRadius: 4,
                        background: SEGMENT_COLORS[item.influencerSegment] ?? '#94a3b8',
                        color: '#fff',
                      }}>
                        {SEGMENT_LABELS[item.influencerSegment] ?? item.influencerSegment}
                      </span>
                      <span style={{ fontSize: 10, color: '#cbd5e1' }}>/</span>
                      <span style={{
                        display: 'inline-block', fontSize: 10, fontWeight: 600,
                        padding: '1px 6px', borderRadius: 4,
                        background: SEGMENT_COLORS[item.influencedSegment] ?? '#94a3b8',
                        color: '#fff',
                      }}>
                        {SEGMENT_LABELS[item.influencedSegment] ?? item.influencedSegment}
                      </span>
                    </div>
                    {item.snippet && (
                      <p style={{ fontSize: 11, color: '#64748b', marginTop: 4, lineHeight: 1.4, fontStyle: 'italic' }}>
                        &ldquo;{item.snippet.length > 120 ? item.snippet.slice(0, 117) + '\u2026' : item.snippet}&rdquo;
                      </p>
                    )}
                  </div>
                  <div style={{
                    minWidth: 52, textAlign: 'right',
                    fontWeight: 700, fontSize: 14,
                    color: item.delta > 0 ? '#22c55e' : '#ef4444',
                  }}>
                    {item.delta > 0 ? '+' : ''}{item.delta.toFixed(2)}
                  </div>
                </div>
              ))}
            </div>

            {influenceBySegmentData.length > 0 && (
              <div style={{ marginTop: 16 }}>
                <p style={{ fontSize: 11, fontWeight: 600, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 8 }}>
                  Influence Given vs Received by Segment
                </p>
                <ResponsiveContainer width="100%" height={Math.max(120, influenceBySegmentData.length * 36)}>
                  <BarChart data={influenceBySegmentData} layout="vertical" margin={{ top: 0, right: 8, bottom: 0, left: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" horizontal={false} />
                    <XAxis type="number" tick={{ fontSize: 11, fill: '#94a3b8' }} axisLine={false} tickLine={false} />
                    <YAxis
                      type="category"
                      dataKey="label"
                      width={90}
                      tick={{ fontSize: 11, fill: '#64748b' }}
                      axisLine={false}
                      tickLine={false}
                    />
                    <Tooltip cursor={{ fill: '#f8fafc' }} />
                    <Legend wrapperStyle={{ fontSize: 11 }} />
                    <ReferenceLine x={0} stroke="#cbd5e1" />
                    <Bar dataKey="given" fill="#6366f1" name="Given" radius={[0, 3, 3, 0]} />
                    <Bar dataKey="received" fill="#f59e0b" name="Received" radius={[0, 3, 3, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}
          </div>
        )}

        {/* Environmental Influences */}
        {envInfluenceData && envInfluenceData.length > 0 && (
          <div style={{ background: '#fff', border: '1px solid #e2e8f0', borderRadius: 10, padding: 16, boxShadow: '0 1px 3px rgba(0,0,0,0.04)' }}>
            <p style={{ fontSize: 12, fontWeight: 600, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 12 }}>
              Environmental Influences
            </p>
            <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
              {envInfluenceData.map((d, i) => (
                <div key={i} style={{
                  flex: '1 1 140px', minWidth: 140,
                  border: '1px solid #e2e8f0', borderRadius: 8, padding: '10px 14px',
                  background: '#f8fafc',
                }}>
                  <p style={{ fontSize: 11, fontWeight: 600, color: '#475569', margin: '0 0 6px' }}>{d.label}</p>
                  <div style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
                    <span style={{ fontSize: 20, fontWeight: 700, color: '#1e293b' }}>{d.count}</span>
                    <span style={{
                      fontSize: 12, fontWeight: 600,
                      color: (d.delta ?? 0) > 0 ? '#22c55e' : (d.delta ?? 0) < 0 ? '#ef4444' : '#94a3b8',
                    }}>
                      {(d.delta ?? 0) > 0 ? '+' : ''}{(d.delta ?? 0).toFixed(2)}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Platform Segments (sentiment by segment per platform) */}
        {platformSegmentsData.length > 0 && (
          <div style={{ background: '#fff', border: '1px solid #e2e8f0', borderRadius: 10, padding: 16, boxShadow: '0 1px 3px rgba(0,0,0,0.04)' }}>
            <p style={{ fontSize: 12, fontWeight: 600, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 12 }}>
              Platform Segments
            </p>
            <ResponsiveContainer width="100%" height={Math.max(140, platformSegmentsData.length * 32)}>
              <BarChart
                data={platformSegmentsData.map(d => ({
                  name: `${d.platform} - ${d.segment}`,
                  positive: d.positive,
                  neutral: d.neutral,
                  negative: d.negative,
                  constructive_pct: d.constructive_pct,
                  effective_positive_pct: d.effective_positive_pct,
                  total: d.total,
                }))}
                layout="vertical"
                margin={{ top: 0, right: 8, bottom: 0, left: 0 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" horizontal={false} />
                <XAxis type="number" tick={{ fontSize: 11, fill: '#94a3b8' }} axisLine={false} tickLine={false} unit="%" domain={[0, 100]} />
                <YAxis
                  type="category"
                  dataKey="name"
                  width={130}
                  tick={{ fontSize: 10, fill: '#64748b' }}
                  axisLine={false}
                  tickLine={false}
                />
                <Tooltip
                  cursor={{ fill: '#f8fafc' }}
                  // eslint-disable-next-line @typescript-eslint/no-explicit-any
                  formatter={(_v: any, name: any, props: any) => {
                    const d = props?.payload
                    if (name === 'constructive_pct' && d?.constructive_pct) {
                      return [`${d.constructive_pct}%`, 'Constructive']
                    }
                    if (!d) return [`${_v}%`, SENTIMENT_LABELS[name as string] ?? name]
                    const extra = d.constructive_pct ? ` | constructive: ${d.constructive_pct}%` : ''
                    const eff = d.effective_positive_pct ? ` | eff. positive: ${d.effective_positive_pct}%` : ''
                    return [`${_v}% (n=${d.total}${extra}${eff})`, SENTIMENT_LABELS[name as string] ?? name]
                  }}
                />
                <Legend
                  formatter={(value) => {
                    if (value === 'constructive_pct') return 'Constructive'
                    return SENTIMENT_LABELS[value as string] ?? value
                  }}
                  wrapperStyle={{ fontSize: 11 }}
                />
                <Bar dataKey="positive" stackId="a" fill="#22c55e" />
                <Bar dataKey="neutral" stackId="a" fill="#94a3b8" />
                <Bar dataKey="negative" stackId="a" fill="#ef4444" />
                <Bar dataKey="constructive_pct" stackId="a" fill="#3b82f6" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}

        {/* Participant Profile (persona demographics) */}
        {hasPersonaData && (
          <div style={{ background: '#fff', border: '1px solid #e2e8f0', borderRadius: 10, padding: 16, boxShadow: '0 1px 3px rgba(0,0,0,0.04)' }}>
            <p style={{ fontSize: 12, fontWeight: 600, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 12 }}>
              Participant Profile
            </p>

            {/* Total participants */}
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 6, marginBottom: 16 }}>
              <span style={{ fontSize: 28, fontWeight: 700, color: '#1e293b' }}>{allPersonas.length}</span>
              <span style={{ fontSize: 12, color: '#94a3b8' }}>total participants</span>
            </div>

            {/* Seniority distribution bar chart */}
            {seniorityData.length > 0 && (
              <div style={{ marginBottom: 16 }}>
                <p style={{ fontSize: 11, color: '#64748b', fontWeight: 600, marginBottom: 8 }}>Seniority Distribution</p>
                <ResponsiveContainer width="100%" height={Math.max(100, seniorityData.length * 28)}>
                  <BarChart data={seniorityData} layout="vertical" margin={{ top: 0, right: 8, bottom: 0, left: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" horizontal={false} />
                    <XAxis type="number" tick={{ fontSize: 11, fill: '#94a3b8' }} axisLine={false} tickLine={false} allowDecimals={false} />
                    <YAxis type="category" dataKey="name" width={70} tick={{ fontSize: 11, fill: '#64748b' }} axisLine={false} tickLine={false} />
                    <Tooltip cursor={{ fill: '#f8fafc' }} formatter={(v) => [v, 'count']} />
                    <Bar dataKey="count" fill="#8b5cf6" radius={[0, 3, 3, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}

            {/* Affiliation top 5 */}
            {topAffiliations.length > 0 && (
              <div style={{ marginBottom: 16 }}>
                <p style={{ fontSize: 11, color: '#64748b', fontWeight: 600, marginBottom: 8 }}>Top Affiliations</p>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                  {topAffiliations.map(a => (
                    <span key={a.name} style={{
                      fontSize: 11, padding: '3px 10px', borderRadius: 10,
                      background: '#f1f5f9', color: '#475569', fontWeight: 500,
                    }}>
                      {a.name} ({a.count})
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* MBTI distribution bar chart */}
            {mbtiData.length > 0 && (
              <div style={{ marginBottom: 16 }}>
                <p style={{ fontSize: 11, color: '#64748b', fontWeight: 600, marginBottom: 8 }}>MBTI Distribution</p>
                <ResponsiveContainer width="100%" height={Math.max(100, mbtiData.length * 28)}>
                  <BarChart data={mbtiData} layout="vertical" margin={{ top: 0, right: 8, bottom: 0, left: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" horizontal={false} />
                    <XAxis type="number" tick={{ fontSize: 11, fill: '#94a3b8' }} axisLine={false} tickLine={false} allowDecimals={false} />
                    <YAxis type="category" dataKey="name" width={50} tick={{ fontSize: 11, fill: '#64748b' }} axisLine={false} tickLine={false} />
                    <Tooltip cursor={{ fill: '#f8fafc' }} formatter={(v) => [v, 'count']} />
                    <Bar dataKey="count" fill="#06b6d4" radius={[0, 3, 3, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}

            {/* Generation distribution bar chart */}
            {generationData.length > 0 && (
              <div style={{ marginBottom: 16 }}>
                <p style={{ fontSize: 11, color: '#64748b', fontWeight: 600, marginBottom: 8 }}>Generation Distribution</p>
                <ResponsiveContainer width="100%" height={Math.max(100, generationData.length * 28)}>
                  <BarChart data={generationData} layout="vertical" margin={{ top: 0, right: 8, bottom: 0, left: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" horizontal={false} />
                    <XAxis type="number" tick={{ fontSize: 11, fill: '#94a3b8' }} axisLine={false} tickLine={false} allowDecimals={false} />
                    <YAxis type="category" dataKey="name" width={70} tick={{ fontSize: 11, fill: '#64748b' }} axisLine={false} tickLine={false} />
                    <Tooltip cursor={{ fill: '#f8fafc' }} formatter={(v) => [v, 'count']} />
                    <Bar dataKey="count" fill="#f59e0b" radius={[0, 3, 3, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}

            {/* Average traits — horizontal progress bars */}
            {avgTraits && (
              <div>
                <p style={{ fontSize: 11, color: '#64748b', fontWeight: 600, marginBottom: 8 }}>Average Traits (1-10)</p>
                {[
                  { label: 'Skepticism', value: avgTraits.skepticism, color: '#f59e0b' },
                  { label: 'Commercial Focus', value: avgTraits.commercial_focus, color: '#3b82f6' },
                  { label: 'Innovation Openness', value: avgTraits.innovation_openness, color: '#22c55e' },
                ].map(t => (
                  <div key={t.label} style={{ marginBottom: 8 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, marginBottom: 3 }}>
                      <span style={{ color: '#64748b' }}>{t.label}</span>
                      <span style={{ color: '#94a3b8', fontVariantNumeric: 'tabular-nums' }}>{t.value.toFixed(1)}</span>
                    </div>
                    <div style={{ height: 6, borderRadius: 3, background: '#f1f5f9', overflow: 'hidden' }}>
                      <div style={{
                        height: '100%', borderRadius: 3,
                        background: t.color,
                        width: `${(t.value / 10) * 100}%`,
                        transition: 'width 0.4s ease',
                      }} />
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Hot Debate Threads (debate_timeline stacked bar charts) */}
        {debateTimelineItems.length > 0 && (
          <div style={{ background: '#fff', border: '1px solid #e2e8f0', borderRadius: 10, padding: 16, boxShadow: '0 1px 3px rgba(0,0,0,0.04)' }}>
            <p style={{ fontSize: 12, fontWeight: 600, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 12 }}>
              Hot Debate Threads
            </p>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
              {debateTimelineItems.map((debate, idx) => (
                <div key={idx} style={{
                  border: '1px solid #e2e8f0', borderRadius: 8, padding: 16, background: '#f8fafc'
                }}>
                  <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 8 }}>
                    <span style={{ fontSize: 11, padding: '1px 7px', borderRadius: 8, background: '#ede9fe', color: '#7c3aed', fontWeight: 600 }}>
                      {debate.platform}
                    </span>
                    <span style={{ fontSize: 12, color: '#64748b' }}>by {debate.author_name}</span>
                    <span style={{ fontSize: 11, color: '#94a3b8', marginLeft: 'auto' }}>{debate.total_replies} replies</span>
                  </div>
                  <p style={{ fontSize: 12, color: '#475569', marginBottom: 8, lineHeight: 1.5, fontStyle: 'italic' }}>
                    &ldquo;{debate.root_content_snippet}&rdquo;
                  </p>
                  {debate.participant_segments && Object.keys(debate.participant_segments).length > 0 && (
                    <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap', marginBottom: 10 }}>
                      {Object.entries(debate.participant_segments)
                        .sort((a, b) => b[1] - a[1])
                        .slice(0, 3)
                        .map(([seg, count]) => (
                          <span key={seg} style={{
                            fontSize: 10,
                            padding: '1px 6px',
                            borderRadius: 6,
                            background: (SEGMENT_COLORS[seg] ?? '#94a3b8') + '1a',
                            color: SEGMENT_COLORS[seg] ?? '#64748b',
                            fontWeight: 600,
                          }}>
                            {SEGMENT_ABBREV[seg] || seg}: {count}
                          </span>
                        ))}
                    </div>
                  )}
                  <ResponsiveContainer width="100%" height={120}>
                    <BarChart data={debate.timeline} margin={{ top: 4, right: 8, left: -20, bottom: 0 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                      <XAxis dataKey="round" tick={{ fontSize: 10 }} />
                      <YAxis tick={{ fontSize: 10 }} />
                      <Tooltip contentStyle={{ fontSize: 11 }} />
                      <Bar dataKey="positive" stackId="a" fill={SENTIMENT_COLORS.positive} name="Positive" />
                      <Bar dataKey="constructive" stackId="a" fill={SENTIMENT_COLORS.constructive} name="Constructive" />
                      <Bar dataKey="neutral" stackId="a" fill={SENTIMENT_COLORS.neutral} name="Neutral" />
                      <Bar dataKey="negative" stackId="a" fill={SENTIMENT_COLORS.negative} name="Negative" />
                      {debate.turning_points?.map((tp, tpIdx) => (
                        <ReferenceLine
                          key={tpIdx}
                          x={tp.round}
                          stroke={tp.direction === 'positive' ? SENTIMENT_COLORS.positive : SENTIMENT_COLORS.negative}
                          strokeDasharray="4 2"
                          label={{ value: tp.direction === 'positive' ? '\u25B2' : '\u25BC', position: 'top', fontSize: 10 }}
                        />
                      ))}
                    </BarChart>
                  </ResponsiveContainer>
                  {debate.turning_points && debate.turning_points.length > 0 && (
                    <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 8 }}>
                      {debate.turning_points.slice(0, 3).map((tp, tpIdx) => {
                        const isPositive = tp.direction === 'positive'
                        return (
                          <span
                            key={tpIdx}
                            title={tp.trigger_snippet || ''}
                            style={{
                              fontSize: 11,
                              padding: '2px 8px',
                              borderRadius: 6,
                              fontWeight: 600,
                              background: isPositive ? '#dcfce7' : '#fee2e2',
                              color: isPositive ? '#16a34a' : '#dc2626',
                              whiteSpace: 'nowrap',
                            }}
                          >
                            R{tp.round} {isPositive ? '\u2191' : '\u2193'}{Math.abs(tp.delta_pct ?? 0).toFixed(1)}%{tp.trigger_author ? ` by @${tp.trigger_author}` : ''}
                          </span>
                        )
                      })}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

      </div>
    </div>
  )
}
