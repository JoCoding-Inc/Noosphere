import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Header } from '../components/Header'
import { useSimulation } from '../hooks/useSimulation'
import { PlatformSimFeed } from '../components/PlatformSimFeed'
import { OntologyGraph } from '../components/OntologyGraph'
import { SOURCE_COLORS } from '../constants'
import { resumeSimulation } from '../api'
import type { Platform, SocialPost } from '../types'

const PLATFORM_COLORS: Record<Platform, string> = {
  hackernews: '#f97316',
  producthunt: '#ef4444',
  indiehackers: '#8b5cf6',
  reddit_startups: '#b45309',
  linkedin: '#2563eb',
}

export function SimulatePage() {
  const { simId } = useParams<{ simId: string }>()
  const navigate = useNavigate()
  const sim = useSimulation(simId!)
  const [isResuming, setIsResuming] = useState(false)
  const [resumeError, setResumeError] = useState<string | null>(null)

  async function handleResume() {
    if (!simId) return
    setIsResuming(true)
    setResumeError(null)
    try {
      await resumeSimulation(simId)
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

  const lastProgress = sim.events
    .filter(e => e.type === 'sim_progress')
    .map(e => (e as { type: 'sim_progress'; message: string }).message)
    .at(-1)

  const totalPosts = Object.values(sim.postsByPlatform).reduce((s, a) => s + (a?.length ?? 0), 0)

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
          style={{ margin: 0, fontSize: 20, fontWeight: 700, letterSpacing: '-0.02em' }}
        >
          {phaseLabel[phase]}
        </h2>
      </div>

      {/* 현재 진행 메시지 */}
      {lastProgress && (
        <p key={lastProgress} style={{
          color: '#64748b', fontSize: 13, margin: '0 0 20px 22px',
          animation: 'fadeIn 0.3s ease',
        }}>
          {lastProgress}
        </p>
      )}

      {sim.status === 'error' && (
        <div style={{ margin: '8px 0 20px' }}>
          <p style={{ color: '#ef4444', fontSize: 14, margin: '0 0 12px' }}>{sim.errorMsg}</p>
          {sim.lastRound > 0 && (
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
          {resumeError && (
            <p style={{ color: '#ef4444', fontSize: 13, margin: '8px 0 0' }}>{resumeError}</p>
          )}
        </div>
      )}

      {/* 페르소나 생성 진행 바 */}
      {phase === 'personas' && sim.agentCount > 0 && (
        <div style={{ margin: '0 0 24px 0', animation: 'fadeInUp 0.3s ease' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, color: '#94a3b8', marginBottom: 6 }}>
            <span>Building agent personas</span>
            <span>{sim.personaCount} created</span>
          </div>
          <div style={{ height: 6, background: '#e2e8f0', borderRadius: 3, overflow: 'hidden' }}>
            <div style={{
              height: '100%', borderRadius: 3,
              background: 'linear-gradient(90deg, #8b5cf6, #6366f1)',
              width: `${personaPct}%`,
              transition: 'width 0.4s ease',
              boxShadow: '0 0 8px rgba(139,92,246,0.5)',
            }} />
          </div>
        </div>
      )}

      {/* 플랫폼별 포스트 카운터 */}
      {totalPosts > 0 && (
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 20 }}>
          {(Object.entries(sim.postsByPlatform) as [Platform, SocialPost[]][]).map(([platform, posts]) => (
            <span key={platform} style={{
              fontSize: 12, padding: '4px 10px', borderRadius: 20,
              background: '#f1f5f9', color: '#475569',
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

      {/* 플랫폼별 시뮬레이션 피드 */}
      {totalPosts > 0 && (
        <div style={{ borderTop: '1px solid #e2e8f0', paddingTop: 20 }}>
          <PlatformSimFeed postsByPlatform={sim.postsByPlatform} />
        </div>
      )}

      {/* 초기 대기 상태 */}
      {totalPosts === 0 && sim.sourceTimeline.length === 0 && phase !== 'error' && (
        <div style={{
          marginTop: 48, textAlign: 'center', color: '#94a3b8', fontSize: 14,
          animation: 'fadeIn 0.5s ease',
        }}>
          <div style={{ fontSize: 28, marginBottom: 12 }}>⚙️</div>
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

      {sim.ontology ? (
        /* 2컬럼 레이아웃 — 온톨로지 수신 후 */
        <main className="page-enter" style={{
          maxWidth: 1280, margin: '0 auto', padding: '16px 24px',
          display: 'flex', gap: 24, alignItems: 'flex-start',
        }}>
          {/* 좌측: Ecosystem Map (sticky) */}
          <div style={{
            width: 420, flexShrink: 0,
            position: 'sticky', top: 8,
            animation: 'fadeInUp 0.4s ease',
          }}>
            <p style={{ fontSize: 11, fontWeight: 700, color: '#94a3b8', letterSpacing: '0.06em', textTransform: 'uppercase', margin: '0 0 10px' }}>
              Ecosystem Map
            </p>
            <OntologyGraph
              data={sim.ontology}
              contextNodes={[]}
              width={420}
            />
          </div>

          {/* 우측: 시뮬레이션 피드 */}
          <div style={{ flex: 1, minWidth: 0, paddingTop: 4 }}>
            {feedPanel}
          </div>
        </main>
      ) : (
        /* 1컬럼 레이아웃 — 온톨로지 수신 전 */
        <main className="page-enter" style={{ maxWidth: 720, margin: '0 auto', padding: '48px 24px' }}>
          {feedPanel}
        </main>
      )}
    </div>
  )
}
