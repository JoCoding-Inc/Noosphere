import { useEffect, useMemo, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { LineChart, Line, ResponsiveContainer, Tooltip } from 'recharts'
import { Header } from '../components/Header'
import { useSimulation } from '../hooks/useSimulation'
import { PlatformSimFeed } from '../components/PlatformSimFeed'
import { ContextGraph } from '../components/OntologyGraph'
import { SOURCE_COLORS, PLATFORM_COLORS } from '../constants'
import { resumeSimulation, cancelSimulation } from '../api'
import { t } from '../tokens'
import type { Platform, SocialPost } from '../types'

export function SimulatePage() {
  const { simId } = useParams<{ simId: string }>()
  const navigate = useNavigate()
  const sim = useSimulation(simId!)
  const [isResuming, setIsResuming] = useState(false)
  const [resumeError, setResumeError] = useState<string | null>(null)
  const [isCancelling, setIsCancelling] = useState(false)
  const [cancelError, setCancelError] = useState<string | null>(null)
  const [selectedRound, setSelectedRound] = useState(0)

  async function handleCancel() {
    if (!simId) return
    setIsCancelling(true)
    setCancelError(null)
    try {
      await cancelSimulation(simId)
      // Backend will close the SSE stream, triggering status update automatically
    } catch (e) {
      setCancelError(e instanceof Error ? e.message : 'Failed to cancel')
    } finally {
      setIsCancelling(false)
    }
  }

  async function handleResume() {
    if (!simId) return
    setIsResuming(true)
    setResumeError(null)
    try {
      await resumeSimulation(simId)
      sim.reconnect()
    } catch (e) {
      setResumeError(e instanceof Error ? e.message : 'Resume failed')
    } finally {
      setIsResuming(false)
    }
  }

  useEffect(() => {
    if (sim.status === 'done' && simId) {
      navigate(`/result/${simId}`)
    }
  }, [sim.status, simId, navigate])

  const lastProgress = useMemo(() => {
    for (let index = sim.events.length - 1; index >= 0; index -= 1) {
      const event = sim.events[index]
      if (event.type === 'sim_progress') return event.message
    }
    return undefined
  }, [sim.events])

  const filteredPostsByPlatform = useMemo(() => {
    if (selectedRound === 0) return sim.postsByPlatform
    const filtered: Partial<Record<Platform, SocialPost[]>> = {}
    for (const [platform, posts] of Object.entries(sim.postsByPlatform)) {
      const matching = (posts ?? []).filter(p => p.round_num === selectedRound)
      if (matching.length > 0) filtered[platform as Platform] = matching
    }
    return filtered
  }, [sim.postsByPlatform, selectedRound])

  const roundOptions = useMemo(() => {
    const rounds = new Set<number>()
    for (const posts of Object.values(sim.postsByPlatform)) {
      for (const p of posts ?? []) {
        if (p.round_num > 0) rounds.add(p.round_num)
      }
    }
    return Array.from(rounds).sort((a, b) => a - b)
  }, [sim.postsByPlatform])

  const totalPosts = Object.values(sim.postsByPlatform).reduce((s, a) => s + (a?.length ?? 0), 0)

  const liveSentimentCounts = useMemo(() => {
    const all = Object.values(sim.postsByPlatform).flatMap(list => list ?? [])
    return all.reduce(
      (acc, p) => {
        if (p.sentiment === 'positive') acc.positive++
        else if (p.sentiment === 'neutral') acc.neutral++
        else if (p.sentiment === 'negative') acc.negative++
        return acc
      },
      { positive: 0, neutral: 0, negative: 0 }
    )
  }, [sim.postsByPlatform])

  const phase =
    sim.status === 'error' ? 'error' :
    sim.status === 'connecting' && sim.sourceTimeline.length === 0 && !sim.isSourcing ? 'connecting' :
    sim.agentCount === 0 ? 'sourcing' :
    sim.roundNum === 0 && totalPosts === 0 ? 'personas' :
    sim.roundNum === 0 ? 'seeding' :
    'rounds'

  const phaseLabel: Record<string, string> = {
    connecting: 'Connecting...',
    sourcing: 'Searching sources...',
    personas: 'Generating personas...',
    seeding: 'Initializing platforms...',
    rounds: `Round ${sim.roundNum} · ${totalPosts} posts`,
    error: 'Simulation failed',
  }

  const personaPct = sim.agentCount > 0
    ? Math.min(100, (sim.personaCount / sim.agentCount) * 100)
    : 0

  // 피드 영역 (상태 헤더 + 소스 타임라인 + 시뮬 피드)
  const feedPanel = (
    <>
      {/* 상태 헤더 */}
      <div style={{ display: 'flex', alignItems: 'center', gap: t.space[3], marginBottom: t.space[2] }}>
        {sim.status !== 'error' && (
          <span style={{
            display: 'inline-block', width: 10, height: 10, borderRadius: '50%',
            background: t.color.success, flexShrink: 0,
            animation: 'pulse 1.5s infinite',
          }} />
        )}
        <h2
          className={phase !== 'error' ? 'cursor-blink' : undefined}
          style={{ margin: 0, fontSize: t.font.size['2xl'], fontWeight: t.font.weight.bold, letterSpacing: '-0.02em', flex: 1 }}
        >
          {phaseLabel[phase]}
        </h2>
        {(sim.status === 'running' || sim.status === 'connecting') && phase !== 'error' && (
          <button
            onClick={handleCancel}
            disabled={isCancelling}
            style={{
              display: 'inline-flex', alignItems: 'center', gap: 5,
              padding: `${t.space[1]} ${t.space[3]}`, fontSize: t.font.size.md, fontWeight: t.font.weight.semibold,
              borderRadius: t.radius.md, border: `1px solid #fca5a5`,
              background: isCancelling ? '#fef2f2' : t.color.bgPage,
              color: t.color.danger, cursor: isCancelling ? 'not-allowed' : 'pointer',
              opacity: isCancelling ? 0.6 : 1,
              transition: 'all 0.15s',
              flexShrink: 0,
            }}
          >
            {isCancelling ? 'Stopping...' : '■ Stop'}
          </button>
        )}
      </div>
      {cancelError && (
        <p role="alert" style={{ color: t.color.danger, fontSize: t.font.size.md, margin: `0 0 ${t.space[2]}` }}>{cancelError}</p>
      )}

      {/* Warning 배너 */}
      {sim.warnings.length > 0 && (
        <div style={{
          display: 'flex', flexDirection: 'column', gap: 6,
          margin: `0 0 ${t.space[4]} 0`,
        }}>
          {sim.warnings.map((w, i) => (
            <div key={i} style={{
              display: 'flex', alignItems: 'flex-start', gap: t.space[2],
              background: '#fffbeb', color: '#b45309',
              border: '1px solid #fde68a', borderRadius: 7,
              fontSize: t.font.size.sm, padding: `${t.space[2]} ${t.space[3]}`,
              animation: 'fadeIn 0.3s ease',
            }}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ flexShrink: 0, marginTop: 1 }} aria-hidden="true">
                <path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/>
                <line x1="12" y1="9" x2="12" y2="13"/>
                <line x1="12" y1="17" x2="12.01" y2="17"/>
              </svg>
              <span>{w}</span>
            </div>
          ))}
        </div>
      )}

      {/* 현재 진행 메시지 */}
      {lastProgress && (
        <p key={lastProgress} style={{
          color: t.color.textSecondary, fontSize: t.font.size.md, margin: `0 0 ${t.space[5]} 22px`,
          animation: 'fadeIn 0.3s ease',
        }}>
          {lastProgress}
        </p>
      )}

      {/* 이메일 발송 안내 배너 */}
      {(sim.status === 'running' || sim.status === 'connecting') &&
        import.meta.env.VITE_CLERK_PUBLISHABLE_KEY && (
        <div style={{
          display: 'flex', alignItems: 'center', gap: t.space[2],
          background: '#f0f9ff', color: '#0284c7',
          border: '1px solid #bae6fd', borderRadius: 7,
          fontSize: t.font.size.sm, padding: `${t.space[2]} ${t.space[3]}`,
          margin: `0 0 ${t.space[5]} 0`,
          animation: 'fadeIn 0.4s ease',
        }}>
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ flexShrink: 0 }} aria-hidden="true"><rect x="2" y="4" width="20" height="16" rx="2"/><path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7"/></svg>
          <span>
            We'll send the completed report to your registered email address.
            {' '}
            <span style={{ color: '#0369a1', opacity: 0.75 }}>
              (The completed report will be sent to your registered email address.)
            </span>
          </span>
        </div>
      )}

      {sim.status === 'error' && (
        <div style={{ margin: `${t.space[2]} 0 ${t.space[5]}` }}>
          <p role="alert" style={{ color: t.color.danger, fontSize: t.font.size.lg, margin: `0 0 ${t.space[3]}` }}>{sim.errorMsg}</p>
          {sim.canResume && (
            <div style={{ display: 'flex', alignItems: 'center', gap: t.space[3] }}>
              <p style={{ fontSize: t.font.size.md, color: t.color.textSecondary, margin: 0 }}>
                Saved up to round {sim.lastRound}
              </p>
              <button
                onClick={handleResume}
                disabled={isResuming}
                style={{
                  padding: `${t.space[2]} ${t.space[4]}`, borderRadius: t.radius.md, border: 'none',
                  background: t.color.primary, color: t.color.textInverse, fontWeight: t.font.weight.semibold,
                  fontSize: t.font.size.lg, cursor: isResuming ? 'not-allowed' : 'pointer',
                  opacity: isResuming ? 0.7 : 1,
                }}
              >
                {isResuming ? 'Resuming...' : `Resume from round ${sim.lastRound + 1}`}
              </button>
            </div>
          )}
          {!sim.canResume && sim.backendStatus === 'running' && (
            <p style={{ fontSize: t.font.size.md, color: t.color.textSecondary, margin: 0 }}>
              Connection lost, but the simulation may still be running.
            </p>
          )}
          {resumeError && (
            <p role="alert" style={{ color: t.color.danger, fontSize: t.font.size.md, margin: `${t.space[2]} 0 0` }}>{resumeError}</p>
          )}
          {phase === 'error' && totalPosts > 0 && (
            <div style={{
              display: 'flex', alignItems: 'center', gap: t.space[2],
              background: '#f0f9ff', color: '#0369a1',
              border: '1px solid #bae6fd', borderRadius: 7,
              fontSize: t.font.size.md, padding: `${t.space[2]} ${t.space[3]}`,
              marginTop: t.space[3],
            }}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ flexShrink: 0 }} aria-hidden="true">
                <circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/>
              </svg>
              <span>Partial results available — {totalPosts} posts collected across {sim.roundNum ?? 0} rounds</span>
            </div>
          )}
        </div>
      )}


      {/* 플랫폼별 포스트 카운터 */}
      {totalPosts > 0 && (
        <div style={{ display: 'flex', gap: t.space[2], flexWrap: 'wrap', marginBottom: t.space[5] }}>
          {(Object.entries(sim.postsByPlatform) as [Platform, SocialPost[]][]).map(([platform, posts]) => (
            <span key={platform} style={{
              fontSize: t.font.size.sm, padding: `${t.space[1]} ${t.space[2]}`, borderRadius: t.radius.pill,
              background: '#fafbff', color: '#475569',
              border: '1px solid #e8eaf6',
              display: 'flex', alignItems: 'center', gap: 5,
              animation: 'scaleIn 0.2s ease',
            }}>
              <span style={{
                width: 7, height: 7, borderRadius: '50%', flexShrink: 0,
                background: PLATFORM_COLORS[platform] || '#94a3b8',
              }} />
              {platform} · {posts?.length ?? 0}
            </span>
          ))}
        </div>
      )}

      {/* 소스 수집 타임라인 */}
      {sim.sourceTimeline.length > 0 && phase === 'sourcing' && (
        <div style={{ marginBottom: t.space[5] }}>
          <div style={{ fontSize: t.font.size.xs, color: t.color.textMuted, marginBottom: t.space[2], fontVariantNumeric: 'tabular-nums' }}>
            {sim.sourceTimeline.length} items collected
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {sim.sourceTimeline.map((item, i) => (
              <div
                key={`${item.source}-${i}`}
                className="source-item"
                style={{
                  padding: `${t.space[2]} ${t.space[3]}`, borderRadius: t.radius.md,
                  background: t.color.bgPage, border: `1px solid ${t.color.border}`,
                  boxShadow: 'var(--shadow-card)',
                  borderLeft: `3px solid ${SOURCE_COLORS[item.source] || t.color.textMuted}`,
                  animationDelay: i === 0 ? '0ms' : undefined,
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 3 }}>
                  <span style={{
                    fontSize: 10, fontWeight: t.font.weight.bold, padding: `${t.space[1]} ${t.space[1]}`, borderRadius: t.radius.md,
                    background: SOURCE_COLORS[item.source] ? `${SOURCE_COLORS[item.source]}18` : t.color.bgSubtle,
                    color: SOURCE_COLORS[item.source] || t.color.textSecondary,
                    textTransform: 'uppercase', letterSpacing: '0.04em',
                  }}>
                    {item.source}
                  </span>
                </div>
                <div style={{ fontSize: t.font.size.md, fontWeight: t.font.weight.semibold, color: t.color.textPrimary, lineHeight: 1.4 }}>
                  {item.title}
                </div>
                {item.snippet && (
                  <div style={{ fontSize: t.font.size.sm, color: t.color.textSecondary, marginTop: 3, lineHeight: 1.5 }}>
                    {item.snippet}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 라운드 필터 */}
      {totalPosts > 0 && sim.roundNum > 0 && roundOptions.length > 0 && (
        <div style={{ display: 'flex', alignItems: 'center', gap: t.space[2], marginBottom: t.space[3] }}>
          <label htmlFor="round-filter" style={{ fontSize: t.font.size.sm, color: t.color.textSecondary, fontWeight: t.font.weight.semibold, flexShrink: 0 }}>
            Round:
          </label>
          <select
            id="round-filter"
            value={selectedRound}
            onChange={e => setSelectedRound(Number(e.target.value))}
            style={{
              fontSize: t.font.size.sm, padding: `${t.space[1]} ${t.space[2]}`, borderRadius: t.radius.sm,
              border: `1px solid ${t.color.border}`, background: t.color.bgPage, color: t.color.textPrimary,
              cursor: 'pointer',
            }}
          >
            <option value={0}>All Rounds</option>
            {roundOptions.map(r => (
              <option key={r} value={r}>Round {r}</option>
            ))}
          </select>
        </div>
      )}

      {/* Live Sentiment Gauge */}
      {(phase === 'rounds' || (phase === 'error' && totalPosts > 0)) && (() => {
        const { positive, neutral, negative } = liveSentimentCounts
        const total = positive + neutral + negative
        if (total === 0) return null
        const pPct = Math.round((positive / total) * 100)
        const nPct = Math.round((neutral / total) * 100)
        const gPct = Math.round((negative / total) * 100)
        return (
          <div style={{ marginBottom: t.space[4] }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: t.font.size.xs, color: t.color.textMuted, marginBottom: 4 }}>
              <span>Live Sentiment</span>
              <span>{total} posts analyzed</span>
            </div>
            <div style={{ display: 'flex', height: 8, borderRadius: 4, overflow: 'hidden', background: t.color.border }}>
              {pPct > 0 && <div style={{ width: `${pPct}%`, background: t.color.success, transition: 'width 0.3s ease' }} />}
              {nPct > 0 && <div style={{ width: `${nPct}%`, background: t.color.textMuted, transition: 'width 0.3s ease' }} />}
              {gPct > 0 && <div style={{ width: `${gPct}%`, background: t.color.danger, transition: 'width 0.3s ease' }} />}
            </div>
            <div style={{ display: 'flex', gap: t.space[3], marginTop: 4, fontSize: 10, color: t.color.textSecondary }}>
              <span style={{ display: 'flex', alignItems: 'center', gap: 3 }}>
                <span style={{ width: 6, height: 6, borderRadius: '50%', background: t.color.success, display: 'inline-block' }} />
                Positive {pPct}%
              </span>
              <span style={{ display: 'flex', alignItems: 'center', gap: 3 }}>
                <span style={{ width: 6, height: 6, borderRadius: '50%', background: t.color.textMuted, display: 'inline-block' }} />
                Neutral {nPct}%
              </span>
              <span style={{ display: 'flex', alignItems: 'center', gap: 3 }}>
                <span style={{ width: 6, height: 6, borderRadius: '50%', background: t.color.danger, display: 'inline-block' }} />
                Negative {gPct}%
              </span>
            </div>
          </div>
        )
      })()}

      {/* Activity Sparkline */}
      {(phase === 'rounds' || (phase === 'error' && totalPosts > 0)) && sim.roundStats.length > 0 && (() => {
        const sparkData = sim.roundStats.map(r => ({
          round: r.round,
          activity: (r.totalNewPosts ?? 0) + (r.totalNewComments ?? 0),
        }))
        const lastStat = sim.roundStats[sim.roundStats.length - 1]
        const observing = lastStat.pass_count != null || lastStat.inactive_count != null
          ? (lastStat.pass_count ?? 0) + (lastStat.inactive_count ?? 0)
          : null
        return (
          <div style={{ marginBottom: t.space[4] }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: t.font.size.xs, color: t.color.textMuted, marginBottom: 4 }}>
              <span>Activity per Round</span>
              {observing != null && observing > 0 && (
                <span>{observing} agents observing this round</span>
              )}
            </div>
            <div style={{ width: '100%', height: 80 }}>
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={sparkData} margin={{ top: 4, right: 4, bottom: 4, left: 4 }}>
                  <Line
                    type="monotone"
                    dataKey="activity"
                    stroke="#6366f1"
                    strokeWidth={2}
                    dot={false}
                    isAnimationActive={false}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>
        )
      })()}

      {/* Sentiment Sparkline */}
      {(phase === 'rounds' || (phase === 'error' && totalPosts > 0)) && sim.roundStats.length >= 2 && (() => {
        const sentimentByRound: Record<number, { positive: number; negative: number }> = {}
        for (const posts of Object.values(sim.postsByPlatform)) {
          for (const p of posts ?? []) {
            if (p.round_num <= 0) continue
            if (!sentimentByRound[p.round_num]) sentimentByRound[p.round_num] = { positive: 0, negative: 0 }
            if (p.sentiment === 'positive') sentimentByRound[p.round_num].positive += 1
            else if (p.sentiment === 'negative') sentimentByRound[p.round_num].negative += 1
          }
        }
        const chartData = sim.roundStats.map(r => ({
          round: r.round,
          positive: sentimentByRound[r.round]?.positive ?? 0,
          negative: sentimentByRound[r.round]?.negative ?? 0,
        }))
        if (chartData.every(d => d.positive === 0 && d.negative === 0)) return null
        const lastStat = sim.roundStats[sim.roundStats.length - 1]
        const convergence = lastStat.convergence_score
        return (
          <div style={{ marginBottom: t.space[4] }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: t.font.size.xs, color: t.color.textMuted, marginBottom: 4 }}>
              <span>Sentiment Trend</span>
              {convergence != null && (
                <span style={{ fontSize: t.font.size.xs, fontWeight: t.font.weight.semibold, color: t.color.primary }}>
                  Convergence: {Math.round(convergence * 100)}%
                </span>
              )}
            </div>
            <div style={{ width: '100%', height: 80 }}>
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chartData} margin={{ top: 4, right: 4, bottom: 4, left: 4 }}>
                  <Line type="monotone" dataKey="positive" stroke="#22c55e" strokeWidth={2} dot={false} isAnimationActive={false} />
                  <Line type="monotone" dataKey="negative" stroke="#ef4444" strokeWidth={2} dot={false} isAnimationActive={false} />
                  <Tooltip
                    contentStyle={{ background: t.color.textPrimary, border: 'none', borderRadius: 6, fontSize: 11, color: t.color.border }}
                    labelStyle={{ color: t.color.textMuted, fontSize: 10 }}
                    labelFormatter={(v) => `Round ${v}`}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
            <div style={{ display: 'flex', gap: t.space[3], marginTop: 2, fontSize: 10, color: t.color.textSecondary }}>
              <span style={{ display: 'flex', alignItems: 'center', gap: 3 }}>
                <span style={{ width: 6, height: 6, borderRadius: '50%', background: t.color.success, display: 'inline-block' }} />
                Positive
              </span>
              <span style={{ display: 'flex', alignItems: 'center', gap: 3 }}>
                <span style={{ width: 6, height: 6, borderRadius: '50%', background: t.color.danger, display: 'inline-block' }} />
                Negative
              </span>
            </div>
          </div>
        )
      })()}

      {/* Segment Distribution Mini-Bar */}
      {(phase === 'rounds' || (phase === 'error' && totalPosts > 0)) && sim.segmentDistribution && (() => {
        const entries = Object.entries(sim.segmentDistribution)
        const total = entries.reduce((s, [, v]) => s + v, 0)
        if (total === 0) return null
        const SEGMENT_COLORS = [t.color.primary, t.color.warning, t.color.success, t.color.danger, '#8b5cf6', '#14b8a6', '#f97316', '#ec4899']
        return (
          <div style={{ marginBottom: t.space[4] }}>
            <div style={{ fontSize: t.font.size.xs, color: t.color.textMuted, marginBottom: 4 }}>Segment Distribution</div>
            <div style={{ display: 'flex', height: 8, borderRadius: 4, overflow: 'hidden', background: t.color.border }}>
              {entries.map(([name, count], i) => (
                <div
                  key={name}
                  style={{
                    width: `${(count / total) * 100}%`,
                    background: SEGMENT_COLORS[i % SEGMENT_COLORS.length],
                    transition: 'width 0.3s ease',
                  }}
                  title={`${name}: ${count} (${Math.round((count / total) * 100)}%)`}
                />
              ))}
            </div>
            <div style={{ display: 'flex', gap: 10, marginTop: 4, flexWrap: 'wrap' }}>
              {entries.map(([name, count], i) => (
                <span key={name} style={{ display: 'flex', alignItems: 'center', gap: 3, fontSize: 10, color: t.color.textSecondary }}>
                  <span style={{ width: 6, height: 6, borderRadius: '50%', background: SEGMENT_COLORS[i % SEGMENT_COLORS.length], display: 'inline-block' }} />
                  {name} {Math.round((count / total) * 100)}%
                </span>
              ))}
            </div>
          </div>
        )
      })()}

      {/* Early Stop Banner */}
      {sim.earlyStop && (phase === 'rounds' || (phase === 'error' && totalPosts > 0)) && (
        <div style={{
          display: 'flex', alignItems: 'center', gap: t.space[2],
          background: '#fffbeb', color: '#92400e',
          border: '1px solid #fde68a', borderRadius: 7,
          fontSize: t.font.size.md, fontWeight: t.font.weight.semibold, padding: `${t.space[2]} ${t.space[3]}`,
          margin: `0 0 ${t.space[4]} 0`,
          animation: 'fadeIn 0.3s ease',
        }}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#f59e0b" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ flexShrink: 0 }} aria-hidden="true">
            <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>
            <polyline points="22 4 12 14.01 9 11.01"/>
          </svg>
          Simulation converged at round {sim.earlyStop.stoppedAtRound} — proceeding to report...
        </div>
      )}

      {/* ETA 표시 — only during active rounds, not on error */}
      {!sim.earlyStop && sim.eta && sim.eta.etaSeconds > 0 && phase === 'rounds' && (
        <p style={{ fontSize: t.font.size.md, color: t.color.textMuted, margin: `0 0 ${t.space[4]} 0` }}>
          {sim.eta.etaSeconds < 60
            ? `~${sim.eta.etaSeconds}s remaining`
            : `~${Math.ceil(sim.eta.etaSeconds / 60)}m remaining`}
          {' '}({sim.eta.completedRounds}/{sim.eta.totalRounds} rounds)
        </p>
      )}

      {/* 플랫폼별 시뮬레이션 피드 */}
      {totalPosts > 0 && (
        <div style={{ borderTop: `1px solid ${t.color.border}`, paddingTop: t.space[5] }}>
          <PlatformSimFeed postsByPlatform={filteredPostsByPlatform} />
        </div>
      )}

      {/* 초기 대기 상태 */}
      {totalPosts === 0 && sim.sourceTimeline.length === 0 && phase !== 'error' && (
        <div style={{
          marginTop: 48, textAlign: 'center', color: t.color.textMuted, fontSize: t.font.size.lg,
          animation: 'fadeIn 0.5s ease',
        }}>
          {sim.queuePosition !== null && sim.queuePosition > 0 ? (
            /* 큐 대기 중 */
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: t.space[4] }}>
              <div style={{
                width: 64, height: 64, borderRadius: '50%',
                background: 'linear-gradient(135deg, #ede9fe 0%, #ddd6fe 100%)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
              }}>
                <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#7c3aed" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>
                </svg>
              </div>
              <div>
                <div style={{ fontSize: 28, fontWeight: 800, color: t.color.primary, lineHeight: 1 }}>
                  #{sim.queuePosition}
                </div>
                <div style={{ fontSize: t.font.size.md, color: t.color.textSecondary, marginTop: 6 }}>in queue</div>
              </div>
              <div style={{
                background: t.color.bgCard, border: `1px solid ${t.color.border}`, borderRadius: t.radius.lg,
                padding: `${t.space[3]} ${t.space[5]}`, maxWidth: 320,
              }}>
                <p style={{ margin: 0, fontSize: t.font.size.md, color: '#475569', lineHeight: 1.6 }}>
                  Another simulation is currently running. Yours will start automatically when it's done.
                </p>
              </div>
              <div style={{ display: 'flex', gap: 6, marginTop: t.space[1] }}>
                {[0, 1, 2].map(i => (
                  <div key={i} style={{
                    width: 6, height: 6, borderRadius: '50%', background: t.color.primary,
                    animation: `pulse 1.2s ease-in-out ${i * 0.2}s infinite`,
                  }} />
                ))}
              </div>
            </div>
          ) : (
            <>
              <div style={{ marginBottom: t.space[3], display: 'flex', justifyContent: 'center' }}>
                <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"/><circle cx="12" cy="12" r="3"/></svg>
              </div>
              {phase === 'personas'
                ? `Building ${sim.agentCount} agent personas across platforms...`
                : phase === 'seeding'
                ? 'Generating seed posts for each platform...'
                : 'Waiting for simulation to start...'}
            </>
          )}
        </div>
      )}
    </>
  )

  return (
    <div style={{ minHeight: '100vh', background: t.color.bgCard }}>
      <Header />

      {sim.isSourcing ? (
        /* 소싱 단계: 왼쪽 그래프 + 오른쪽 소스 타임라인 */
        <main className="page-enter sim-sourcing-layout" style={{
          maxWidth: 1600, margin: '0 auto', padding: `${t.space[4]} ${t.space[6]}`,
          display: 'flex', gap: t.space[6], alignItems: 'flex-start',
        }}>
          <div style={{
            flex: 3, minWidth: 0,
            position: 'sticky', top: 8,
            animation: 'fadeInUp 0.4s ease',
          }}>
            <p style={{ fontSize: t.font.size.xs, fontWeight: t.font.weight.bold, color: t.color.textMuted, letterSpacing: '0.06em', textTransform: 'uppercase', margin: '0 0 10px' }}>
              Knowledge Graph
            </p>
            <div className="sim-graph-wrapper">
              <ContextGraph
                data={sim.graphData ?? { nodes: [], edges: [] }}
              />
            </div>
          </div>
          <div style={{ flex: 2, minWidth: 0, paddingTop: 4 }}>
            {feedPanel}
          </div>
        </main>
      ) : (
        /* 소싱 이후: 1컬럼 */
        <main className="page-enter" style={{ maxWidth: 900, margin: '0 auto', padding: '48px 24px' }}>
          {feedPanel}
        </main>
      )}
    </div>
  )
}
