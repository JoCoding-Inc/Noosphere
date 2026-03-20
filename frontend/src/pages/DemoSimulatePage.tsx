import { Header } from '../components/Header'
import { useMockSimulation } from '../hooks/useMockSimulation'
import { PlatformSimFeed } from '../components/PlatformSimFeed'

const SOURCE_COLORS: Record<string, string> = {
  github: '#24292e',
  arxiv: '#b91c1c',
  semantic_scholar: '#1d4ed8',
  hackernews: '#f97316',
  reddit: '#ef4444',
  product_hunt: '#da552f',
  itunes: '#fc3158',
  google_play: '#01875f',
  gdelt: '#7c3aed',
  serper: '#0891b2',
}

export function DemoSimulatePage() {
  const sim = useMockSimulation()

  const lastProgress = sim.events
    .filter(e => e.type === 'sim_progress')
    .map(e => (e as { type: 'sim_progress'; message: string }).message)
    .at(-1)

  const totalPosts = Object.values(sim.postsByPlatform).reduce((s, a) => s + (a?.length ?? 0), 0)

  const phase =
    sim.status === 'connecting' ? 'connecting' :
    sim.status === 'error' ? 'error' :
    sim.agentCount === 0 ? 'sourcing' :
    sim.roundNum === 0 && sim.personaCount < sim.agentCount ? 'personas' :
    sim.roundNum === 0 ? 'seeding' :
    'rounds'

  const phaseLabel: Record<string, string> = {
    connecting: 'Connecting...',
    sourcing: 'Searching sources...',
    personas: `Generating personas — ${sim.personaCount} / ${sim.agentCount}`,
    seeding: 'Initializing platforms...',
    rounds: `Round ${sim.roundNum} · ${totalPosts} posts`,
    error: 'Simulation failed',
  }

  const personaPct = sim.agentCount > 0
    ? Math.min(100, (sim.personaCount / sim.agentCount) * 100)
    : 0

  return (
    <div style={{ minHeight: '100vh', background: '#f8fafc' }}>
      <Header />

      {/* 데모 배너 */}
      <div style={{
        background: 'linear-gradient(90deg, #8b5cf6, #6366f1)',
        color: '#fff', textAlign: 'center', fontSize: 12,
        padding: '6px 0', fontWeight: 500, letterSpacing: '0.02em',
      }}>
        ✦ DEMO MODE — preview of live simulation UI
      </div>

      <main className="page-enter" style={{ maxWidth: 720, margin: '0 auto', padding: '48px 24px' }}>

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

        {/* 페르소나 생성 진행 바 */}
        {phase === 'personas' && sim.agentCount > 0 && (
          <div style={{ margin: '0 0 24px 0', animation: 'fadeInUp 0.3s ease' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, color: '#94a3b8', marginBottom: 6 }}>
              <span>Building agent personas</span>
              <span>{sim.personaCount} / {sim.agentCount}</span>
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
            <PlatformSimFeed postsByPlatform={sim.postsByPlatform} ideaText="Noosphere – AI market simulator" />
          </div>
        )}

        {/* 초기 대기 */}
        {totalPosts === 0 && sim.sourceTimeline.length === 0 && phase !== 'error' && (
          <div style={{
            marginTop: 48, textAlign: 'center', color: '#94a3b8', fontSize: 14,
            animation: 'fadeIn 0.5s ease',
          }}>
            <div style={{ fontSize: 28, marginBottom: 12 }}>⚙️</div>
            Waiting for simulation to start...
          </div>
        )}
      </main>
    </div>
  )
}
