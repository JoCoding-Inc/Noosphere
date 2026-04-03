import { useEffect, useMemo, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { LineChart, Line, ResponsiveContainer, Tooltip } from 'recharts'
import { Header } from '../components/Header'
import { useSimulation } from '../hooks/useSimulation'
import { PlatformSimFeed } from '../components/PlatformSimFeed'
import { ContextGraph } from '../components/OntologyGraph'
import { SOURCE_COLORS, PLATFORM_COLORS } from '../constants'
import { resumeSimulation, cancelSimulation } from '../api'
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
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 8 }}>
        {sim.status !== 'error' && (
          <span style={{
            display: 'inline-block', width: 10, height: 10, borderRadius: '50%',
            background: '#22c55e', flexShrink: 0,
            animation: 'pulse 1.5s infinite',
          }} />
        )}
        <h2
          className={phase !== 'error' ? 'cursor-blink' : undefined}
          style={{ margin: 0, fontSize: 20, fontWeight: 700, letterSpacing: '-0.02em', flex: 1 }}
        >
          {phaseLabel[phase]}
        </h2>
        {(sim.status === 'running' || sim.status === 'connecting') && phase !== 'error' && (
          <button
            onClick={handleCancel}
            disabled={isCancelling}
            style={{
              display: 'inline-flex', alignItems: 'center', gap: 5,
              padding: '6px 14px', fontSize: 13, fontWeight: 600,
              borderRadius: 8, border: '1px solid #fca5a5',
              background: isCancelling ? '#fef2f2' : '#fff',
              color: '#ef4444', cursor: isCancelling ? 'not-allowed' : 'pointer',
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
        <p role="alert" style={{ color: '#ef4444', fontSize: 13, margin: '0 0 8px' }}>{cancelError}</p>
      )}

      {/* Warning 배너 */}
      {sim.warnings.length > 0 && (
        <div style={{
          display: 'flex', flexDirection: 'column', gap: 6,
          margin: '0 0 16px 0',
        }}>
          {sim.warnings.map((w, i) => (
            <div key={i} style={{
              display: 'flex', alignItems: 'flex-start', gap: 8,
              background: '#fffbeb', color: '#b45309',
              border: '1px solid #fde68a', borderRadius: 7,
              fontSize: 12, padding: '8px 14px',
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
          color: '#64748b', fontSize: 13, margin: '0 0 20px 22px',
          animation: 'fadeIn 0.3s ease',
        }}>
          {lastProgress}
        </p>
      )}

      {/* 이메일 발송 안내 배너 */}
      {(sim.status === 'running' || sim.status === 'connecting') &&
        import.meta.env.VITE_CLERK_PUBLISHABLE_KEY && (
        <div style={{
          display: 'flex', alignItems: 'center', gap: 8,
          background: '#f0f9ff', color: '#0284c7',
          border: '1px solid #bae6fd', borderRadius: 7,
          fontSize: 12, padding: '8px 14px',
          margin: '0 0 20px 0',
          animation: 'fadeIn 0.4s ease',
        }}>
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ flexShrink: 0 }} aria-hidden="true"><rect x="2" y="4" width="20" height="16" rx="2"/><path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7"/></svg>
          <span>
            We'll send the completed report to your registered email address.
            {' '}
            <span style={{ color: '#0369a1', opacity: 0.75 }}>
              (시뮬레이션이 완료되면 등록된 계정의 이메일로 보고서를 보내드립니다.)
            </span>
          </span>
        </div>
      )}

      {sim.status === 'error' && (
        <div style={{ margin: '8px 0 20px' }}>
          <p role="alert" style={{ color: '#ef4444', fontSize: 14, margin: '0 0 12px' }}>{sim.errorMsg}</p>
          {sim.canResume && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <p style={{ fontSize: 13, color: '#64748b', margin: 0 }}>
                {sim.lastRound}라운드까지 저장됨
              </p>
              <button
                onClick={handleResume}
                disabled={isResuming}
                style={{
                  padding: '8px 18px', borderRadius: 8, border: 'none',
                  background: '#6366f1', color: '#fff', fontWeight: 600,
                  fontSize: 14, cursor: isResuming ? 'not-allowed' : 'pointer',
                  opacity: isResuming ? 0.7 : 1,
                }}
              >
                {isResuming ? '재개 중...' : `${sim.lastRound + 1}라운드부터 재개하기`}
              </button>
            </div>
          )}
          {!sim.canResume && sim.backendStatus === 'running' && (
            <p style={{ fontSize: 13, color: '#64748b', margin: 0 }}>
              연결이 끊겼지만 시뮬레이션은 아직 실행 중일 수 있습니다.
            </p>
          )}
          {resumeError && (
            <p role="alert" style={{ color: '#ef4444', fontSize: 13, margin: '8px 0 0' }}>{resumeError}</p>
          )}
          {phase === 'error' && totalPosts > 0 && (
            <div style={{
              display: 'flex', alignItems: 'center', gap: 8,
              background: '#f0f9ff', color: '#0369a1',
              border: '1px solid #bae6fd', borderRadius: 7,
              fontSize: 13, padding: '8px 14px',
              marginTop: 12,
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
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 20 }}>
          {(Object.entries(sim.postsByPlatform) as [Platform, SocialPost[]][]).map(([platform, posts]) => (
            <span key={platform} style={{
              fontSize: 12, padding: '4px 10px', borderRadius: 20,
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
        <div style={{ marginBottom: 20 }}>
          <div style={{ fontSize: 11, color: '#94a3b8', marginBottom: 8, fontVariantNumeric: 'tabular-nums' }}>
            {sim.sourceTimeline.length} items collected
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {sim.sourceTimeline.map((item, i) => (
              <div
                key={`${item.source}-${i}`}
                className="source-item"
                style={{
                  padding: '8px 12px', borderRadius: 8,
                  background: '#fff', border: '1px solid #e2e8f0',
                  boxShadow: 'var(--shadow-card)',
                  borderLeft: `3px solid ${SOURCE_COLORS[item.source] || '#94a3b8'}`,
                  animationDelay: i === 0 ? '0ms' : undefined,
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 3 }}>
                  <span style={{
                    fontSize: 10, fontWeight: 700, padding: '1px 6px', borderRadius: 8,
                    background: SOURCE_COLORS[item.source] ? `${SOURCE_COLORS[item.source]}18` : '#f1f5f9',
                    color: SOURCE_COLORS[item.source] || '#64748b',
                    textTransform: 'uppercase', letterSpacing: '0.04em',
                  }}>
                    {item.source}
                  </span>
                </div>
                <div style={{ fontSize: 13, fontWeight: 600, color: '#1e293b', lineHeight: 1.4 }}>
                  {item.title}
                </div>
                {item.snippet && (
                  <div style={{ fontSize: 12, color: '#64748b', marginTop: 3, lineHeight: 1.5 }}>
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
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
          <label htmlFor="round-filter" style={{ fontSize: 12, color: '#64748b', fontWeight: 600, flexShrink: 0 }}>
            Round:
          </label>
          <select
            id="round-filter"
            value={selectedRound}
            onChange={e => setSelectedRound(Number(e.target.value))}
            style={{
              fontSize: 12, padding: '4px 8px', borderRadius: 6,
              border: '1px solid #e2e8f0', background: '#fff', color: '#1e293b',
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
          <div style={{ marginBottom: 16 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: '#94a3b8', marginBottom: 4 }}>
              <span>Live Sentiment</span>
              <span>{total} posts analyzed</span>
            </div>
            <div style={{ display: 'flex', height: 8, borderRadius: 4, overflow: 'hidden', background: '#e2e8f0' }}>
              {pPct > 0 && <div style={{ width: `${pPct}%`, background: '#22c55e', transition: 'width 0.3s ease' }} />}
              {nPct > 0 && <div style={{ width: `${nPct}%`, background: '#94a3b8', transition: 'width 0.3s ease' }} />}
              {gPct > 0 && <div style={{ width: `${gPct}%`, background: '#ef4444', transition: 'width 0.3s ease' }} />}
            </div>
            <div style={{ display: 'flex', gap: 12, marginTop: 4, fontSize: 10, color: '#64748b' }}>
              <span style={{ display: 'flex', alignItems: 'center', gap: 3 }}>
                <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#22c55e', display: 'inline-block' }} />
                Positive {pPct}%
              </span>
              <span style={{ display: 'flex', alignItems: 'center', gap: 3 }}>
                <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#94a3b8', display: 'inline-block' }} />
                Neutral {nPct}%
              </span>
              <span style={{ display: 'flex', alignItems: 'center', gap: 3 }}>
                <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#ef4444', display: 'inline-block' }} />
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
          <div style={{ marginBottom: 16 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: '#94a3b8', marginBottom: 4 }}>
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
          <div style={{ marginBottom: 16 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: 11, color: '#94a3b8', marginBottom: 4 }}>
              <span>Sentiment Trend</span>
              {convergence != null && (
                <span style={{ fontSize: 11, fontWeight: 600, color: '#6366f1' }}>
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
                    contentStyle={{ background: '#1e293b', border: 'none', borderRadius: 6, fontSize: 11, color: '#e2e8f0' }}
                    labelStyle={{ color: '#94a3b8', fontSize: 10 }}
                    labelFormatter={(v) => `Round ${v}`}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
            <div style={{ display: 'flex', gap: 12, marginTop: 2, fontSize: 10, color: '#64748b' }}>
              <span style={{ display: 'flex', alignItems: 'center', gap: 3 }}>
                <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#22c55e', display: 'inline-block' }} />
                Positive
              </span>
              <span style={{ display: 'flex', alignItems: 'center', gap: 3 }}>
                <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#ef4444', display: 'inline-block' }} />
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
        const SEGMENT_COLORS = ['#6366f1', '#f59e0b', '#22c55e', '#ef4444', '#8b5cf6', '#14b8a6', '#f97316', '#ec4899']
        return (
          <div style={{ marginBottom: 16 }}>
            <div style={{ fontSize: 11, color: '#94a3b8', marginBottom: 4 }}>Segment Distribution</div>
            <div style={{ display: 'flex', height: 8, borderRadius: 4, overflow: 'hidden', background: '#e2e8f0' }}>
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
                <span key={name} style={{ display: 'flex', alignItems: 'center', gap: 3, fontSize: 10, color: '#64748b' }}>
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
          display: 'flex', alignItems: 'center', gap: 8,
          background: '#fffbeb', color: '#92400e',
          border: '1px solid #fde68a', borderRadius: 7,
          fontSize: 13, fontWeight: 600, padding: '10px 14px',
          margin: '0 0 16px 0',
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
        <p style={{ fontSize: 13, color: '#94a3b8', margin: '0 0 16px 0' }}>
          {sim.eta.etaSeconds < 60
            ? `약 ${sim.eta.etaSeconds}초 남음`
            : `약 ${Math.ceil(sim.eta.etaSeconds / 60)}분 남음`}
          {' '}({sim.eta.completedRounds}/{sim.eta.totalRounds} rounds)
        </p>
      )}

      {/* 플랫폼별 시뮬레이션 피드 */}
      {totalPosts > 0 && (
        <div style={{ borderTop: '1px solid #e2e8f0', paddingTop: 20 }}>
          <PlatformSimFeed postsByPlatform={filteredPostsByPlatform} />
        </div>
      )}

      {/* 초기 대기 상태 */}
      {totalPosts === 0 && sim.sourceTimeline.length === 0 && phase !== 'error' && (
        <div style={{
          marginTop: 48, textAlign: 'center', color: '#94a3b8', fontSize: 14,
          animation: 'fadeIn 0.5s ease',
        }}>
          <div style={{ marginBottom: 12, display: 'flex', justifyContent: 'center' }}>
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"/><circle cx="12" cy="12" r="3"/></svg>
          </div>
          {phase === 'personas'
            ? `Building ${sim.agentCount} agent personas across platforms...`
            : phase === 'seeding'
            ? 'Generating seed posts for each platform...'
            : 'Waiting for simulation to start...'}
        </div>
      )}
    </>
  )

  return (
    <div style={{ minHeight: '100vh', background: '#f8fafc' }}>
      <Header />

      {sim.isSourcing ? (
        /* 소싱 단계: 왼쪽 그래프 + 오른쪽 소스 타임라인 */
        <main className="page-enter sim-sourcing-layout" style={{
          maxWidth: 1600, margin: '0 auto', padding: '16px 24px',
          display: 'flex', gap: 24, alignItems: 'flex-start',
        }}>
          <div style={{
            flex: 3, minWidth: 0,
            position: 'sticky', top: 8,
            animation: 'fadeInUp 0.4s ease',
          }}>
            <p style={{ fontSize: 11, fontWeight: 700, color: '#94a3b8', letterSpacing: '0.06em', textTransform: 'uppercase', margin: '0 0 10px' }}>
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
