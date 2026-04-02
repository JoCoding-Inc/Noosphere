import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Header } from '../components/Header'
import { startSimulation } from '../api'
import { PLATFORM_OPTIONS } from '../constants'
import type { Platform, SimConfig } from '../types'

const LANGUAGE_OPTIONS = [
  { value: 'English',    label: 'English' },
  { value: 'Korean',     label: '한국어' },
  { value: 'Japanese',   label: '日本語' },
  { value: 'Chinese',    label: '中文' },
  { value: 'Spanish',    label: 'Español' },
  { value: 'French',     label: 'Français' },
  { value: 'German',     label: 'Deutsch' },
  { value: 'Portuguese', label: 'Português' },
]

interface SourceDef {
  key: string
  label: string
  defaultVal: number
  max: number
  description: string
}

const SOURCE_GROUPS: Array<{ group: string; sources: SourceDef[] }> = [
  {
    group: 'Code & Academic',
    sources: [
      { key: 'github',           label: 'GitHub',           defaultVal: 60, max: 100, description: 'Repository search results' },
      { key: 'arxiv',            label: 'arXiv',            defaultVal: 60, max: 100, description: 'Academic papers' },
      { key: 'semantic_scholar', label: 'Semantic Scholar', defaultVal: 60, max: 100, description: 'Research citations' },
    ],
  },
  {
    group: 'Communities',
    sources: [
      { key: 'hackernews', label: 'Hacker News', defaultVal: 60, max: 100, description: 'HN posts & comments' },
      { key: 'reddit',     label: 'Reddit',      defaultVal: 60, max: 100, description: 'Subreddit posts' },
    ],
  },
  {
    group: 'Products',
    sources: [
      { key: 'product_hunt', label: 'Product Hunt', defaultVal: 40, max: 60, description: 'Product listings' },
      { key: 'itunes',       label: 'iTunes / App Store', defaultVal: 40, max: 60, description: 'App reviews' },
      { key: 'google_play',  label: 'Google Play', defaultVal: 40, max: 60, description: 'App listings' },
    ],
  },
  {
    group: 'News',
    sources: [
      { key: 'gdelt',  label: 'GDELT',  defaultVal: 30, max: 50, description: 'Global news events' },
      { key: 'serper', label: 'Serper', defaultVal: 20, max: 30, description: 'Web search results' },
    ],
  },
]

const DEFAULT_SOURCE_LIMITS: Record<string, number> = Object.fromEntries(
  SOURCE_GROUPS.flatMap(g => g.sources.map(s => [s.key, s.defaultVal]))
)

const AGENT_OPTIONS = [100, 150, 200] as const

const SIMULATION_PRESETS = [
  { label: 'Quick',    num_rounds: 4,  max_agents: 100, activation_rate: 0.3, description: 'Fast \u00b7 100 agents \u00b7 4 rounds' },
  { label: 'Standard', num_rounds: 8,  max_agents: 150, activation_rate: 0.4, description: 'Balanced \u00b7 150 agents \u00b7 8 rounds' },
  { label: 'Deep',     num_rounds: 12, max_agents: 200, activation_rate: 0.5, description: 'Thorough \u00b7 200 agents \u00b7 12 rounds' },
] as const

const DEFAULT_CONFIG: Omit<SimConfig, 'input_text'> = {
  language: 'English',
  num_rounds: 8,
  max_agents: 150,
  platforms: ['hackernews', 'producthunt', 'indiehackers', 'reddit_startups', 'linkedin'],
  activation_rate: 0.25,
  source_limits: DEFAULT_SOURCE_LIMITS,
}

type OptionsTab = 'simulation' | 'research'

const css = {
  card: {
    background: '#fff',
    border: '1px solid #e2e8f0',
    borderRadius: 12,
    padding: '20px 24px',
    marginBottom: 12,
    boxShadow: 'var(--shadow-card)',
  } as React.CSSProperties,
  sectionTitle: {
    fontSize: 11,
    fontWeight: 700,
    letterSpacing: '0.08em',
    textTransform: 'uppercase' as const,
    color: '#94a3b8',
    marginBottom: 14,
  },
  label: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    fontSize: 14,
    color: '#374151',
    marginBottom: 10,
  } as React.CSSProperties,
  value: {
    fontWeight: 600,
    color: '#1e293b',
    minWidth: 36,
    textAlign: 'right' as const,
  },
  slider: {
    width: '100%',
    marginTop: 4,
    accentColor: '#1e293b',
  } as React.CSSProperties,
  tabBtn: (active: boolean): React.CSSProperties => ({
    padding: '8px 20px',
    fontSize: 13,
    fontWeight: active ? 600 : 400,
    cursor: 'pointer',
    border: 'none',
    borderRadius: 8,
    background: active ? 'var(--primary)' : 'transparent',
    color: active ? '#fff' : '#64748b',
    transition: 'all 0.15s',
  }),
}

export function HomePage() {
  const navigate = useNavigate()
  const [inputText, setInputText] = useState('')
  const [config, setConfig] = useState(DEFAULT_CONFIG)
  const [optionsOpen, setOptionsOpen] = useState(false)
  const [optionsTab, setOptionsTab] = useState<OptionsTab>('simulation')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [activePreset, setActivePreset] = useState<string>('Standard')

  const togglePlatform = (id: Platform) => {
    setConfig(c => ({
      ...c,
      platforms: c.platforms.includes(id)
        ? c.platforms.filter(p => p !== id)
        : [...c.platforms, id],
    }))
  }

  const setLimit = (key: string, val: number) => {
    setConfig(c => ({ ...c, source_limits: { ...c.source_limits, [key]: val } }))
  }

  const handleRun = async () => {
    if (!inputText.trim()) { setError('Please enter a product description.'); return }
    if (config.platforms.length === 0) { setError('Please select at least one platform.'); return }
    setError('')
    setLoading(true)
    try {
      const { sim_id } = await startSimulation({ input_text: inputText, ...config })
      navigate(`/simulate/${sim_id}`)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Unknown error')
      setLoading(false)
    }
  }

  const totalSources = Object.values(config.source_limits).reduce((a, b) => a + b, 0)

  return (
    <div style={{ minHeight: '100vh', background: '#f8fafc' }}>
      <Header />
      <main className="page-enter" style={{ maxWidth: 900, margin: '0 auto', padding: '52px 24px 80px' }}>

        {/* Hero */}
        <div style={{ marginBottom: 32, animation: 'fadeInUp 0.4s ease both' }}>
          <h1 style={{ fontSize: 34, fontWeight: 800, letterSpacing: '-0.04em', margin: '0 0 10px' }}>
            How will the market react?
          </h1>
          <p style={{ color: '#64748b', fontSize: 15, margin: 0 }}>
            Describe your product and simulate real-world reactions across tech communities.
          </p>
        </div>

        {/* Textarea */}
        <textarea
          value={inputText}
          onChange={e => setInputText(e.target.value)}
          placeholder="Paste your landing page copy, pitch deck, or product description here..."
          rows={9}
          style={{
            width: '100%', padding: '16px 18px', fontSize: 15,
            border: '1.5px solid #e2e8f0', borderRadius: 12,
            resize: 'vertical', fontFamily: 'inherit',
            boxSizing: 'border-box', background: '#fff',
            lineHeight: 1.6, outline: 'none',
            transition: 'border-color 0.2s, box-shadow 0.2s',
            animation: 'fadeInUp 0.45s ease both',
          }}
          onFocus={e => {
            e.target.style.borderColor = '#6366f1'
            e.target.style.boxShadow = '0 0 0 3px rgba(99,102,241,0.12)'
          }}
          onBlur={e => {
            e.target.style.borderColor = '#e2e8f0'
            e.target.style.boxShadow = 'none'
          }}
        />

        {/* Char count */}
        {inputText.length > 0 && (
          <div style={{ textAlign: 'right', fontSize: 12, color: '#94a3b8', marginTop: 6 }}>
            {inputText.length.toLocaleString()} characters
          </div>
        )}

        {/* Platforms */}
        <div style={{ marginTop: 16, display: 'flex', gap: 8, flexWrap: 'wrap', animation: 'fadeInUp 0.5s ease both' }}>
          {PLATFORM_OPTIONS.map((p, i) => {
            const active = config.platforms.includes(p.id)
            return (
              <button key={p.id} onClick={() => togglePlatform(p.id)}
                className="platform-btn"
                style={{
                  display: 'flex', alignItems: 'center', gap: 6,
                  padding: '7px 14px', fontSize: 13, borderRadius: 8, cursor: 'pointer',
                  border: '1.5px solid',
                  background: active ? 'var(--primary)' : '#fff',
                  color: active ? '#fff' : '#475569',
                  borderColor: active ? 'var(--primary)' : '#e2e8f0',
                  fontWeight: active ? 600 : 400,
                  boxShadow: active ? '0 2px 8px rgba(99,102,241,0.3)' : 'none',
                  animation: `fadeInUp 0.${50 + i * 5}s ease both`,
                }}>
                {p.label}
              </button>
            )
          })}
        </div>

        {/* Options toggle */}
        <div style={{ marginTop: 20 }}>
          <button
            onClick={() => { setOptionsOpen(o => { if (!o) setOptionsTab('research'); return !o }) }}
            style={{
              display: 'flex', alignItems: 'center', gap: 6,
              background: 'none', border: 'none', cursor: 'pointer',
              color: '#64748b', fontSize: 13, padding: 0,
            }}>
            <span style={{ transition: 'transform 0.2s', display: 'inline-block', transform: optionsOpen ? 'rotate(90deg)' : '' }}>▶</span>
            Advanced options
            <span style={{
              fontSize: 11, padding: '2px 8px', borderRadius: 10,
              background: 'var(--primary-light)', color: '#6366f1', marginLeft: 4,
            }}>
              {config.language} · {config.num_rounds}r · {config.max_agents}a · ~{totalSources} sources
            </span>
          </button>

          {optionsOpen && (
            <div style={{ marginTop: 16 }}>
              {/* Tab bar */}
              <div style={{
                display: 'flex', gap: 4, padding: 4,
                background: '#f1f5f9', borderRadius: 10, width: 'fit-content', marginBottom: 16,
              }}>
                <button style={css.tabBtn(optionsTab === 'research')} onClick={() => setOptionsTab('research')}>
                  Research Sources
                </button>
                <button style={css.tabBtn(optionsTab === 'simulation')} onClick={() => setOptionsTab('simulation')}>
                  Simulation
                </button>
              </div>

              {optionsTab === 'simulation' && (
                <div>
                {/* Preset buttons */}
                <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
                  {SIMULATION_PRESETS.map(preset => {
                    const isActive = activePreset === preset.label
                    return (
                      <button
                        key={preset.label}
                        onClick={() => {
                          setActivePreset(preset.label)
                          setConfig(c => ({
                            ...c,
                            num_rounds: preset.num_rounds,
                            max_agents: preset.max_agents,
                            activation_rate: preset.activation_rate,
                          }))
                        }}
                        style={{
                          flex: 1,
                          padding: '10px 14px',
                          borderRadius: 8,
                          cursor: 'pointer',
                          border: isActive ? '1.5px solid #6366f1' : '1.5px solid #e2e8f0',
                          background: isActive ? '#6366f108' : '#fff',
                          textAlign: 'left',
                          transition: 'all 0.15s',
                        }}
                      >
                        <div style={{
                          fontSize: 13, fontWeight: 600,
                          color: isActive ? '#6366f1' : '#1e293b',
                          marginBottom: 2,
                        }}>
                          {preset.label}
                        </div>
                        <div style={{ fontSize: 11, color: '#94a3b8' }}>
                          {preset.description}
                        </div>
                      </button>
                    )
                  })}
                </div>
                <div className="options-grid" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                  {/* Language */}
                  <div style={css.card}>
                    <div style={css.sectionTitle}>Language</div>
                    <select
                      value={config.language}
                      onChange={e => setConfig(c => ({ ...c, language: e.target.value }))}
                      style={{
                        width: '100%', padding: '8px 12px', fontSize: 14,
                        border: '1px solid #e2e8f0', borderRadius: 8,
                        background: '#fff', cursor: 'pointer', appearance: 'none',
                      }}>
                      {LANGUAGE_OPTIONS.map(l => (
                        <option key={l.value} value={l.value}>{l.label}</option>
                      ))}
                    </select>
                    <p style={{ margin: '8px 0 0', fontSize: 12, color: '#94a3b8' }}>
                      Reports and simulation content will be generated in this language.
                    </p>
                  </div>

                  {/* Rounds */}
                  <div style={css.card}>
                    <div style={css.sectionTitle}>Simulation Rounds</div>
                    <div style={css.label}>
                      <span>Rounds</span>
                      <span style={css.value}>{config.num_rounds}</span>
                    </div>
                    <input type="range" min={1} max={30} step={1}
                      value={config.num_rounds}
                      onChange={e => { setActivePreset(''); setConfig(c => ({ ...c, num_rounds: +e.target.value })) }}
                      style={css.slider} />
                    <p style={{ margin: '8px 0 0', fontSize: 12, color: '#94a3b8' }}>
                      Each round = one wave of agent interactions.
                    </p>
                  </div>

                  {/* Agents */}
                  <div style={css.card}>
                    <div style={css.sectionTitle}>Agent Count</div>
                    <div style={css.label}>
                      <span>Max agents per platform</span>
                    </div>
                    <div style={{ display: 'flex', gap: 8 }}>
                      {AGENT_OPTIONS.map(v => {
                        const selected = config.max_agents === v
                        return (
                          <button
                            key={v}
                            onClick={() => { setActivePreset(''); setConfig(c => ({ ...c, max_agents: v })) }}
                            style={{
                              borderRadius: 8,
                              padding: '8px 20px',
                              fontSize: 14,
                              cursor: 'pointer',
                              background: selected ? '#6366f1' : 'transparent',
                              color: selected ? '#fff' : '#94a3b8',
                              border: selected ? '1.5px solid #6366f1' : '1.5px solid #334155',
                              fontWeight: selected ? 600 : 400,
                            }}>
                            {v}
                          </button>
                        )
                      })}
                    </div>
                    <p style={{ margin: '8px 0 0', fontSize: 12, color: '#94a3b8' }}>
                      100 agents minimum for statistically significant results.
                    </p>
                  </div>

                  {/* Activation Rate */}
                  <div style={css.card}>
                    <div style={css.sectionTitle}>Activation Rate</div>
                    <div style={css.label}>
                      <span>% agents active per round</span>
                      <span style={css.value}>{Math.round(config.activation_rate * 100)}%</span>
                    </div>
                    <input type="range" min={0.1} max={1.0} step={0.05}
                      value={config.activation_rate}
                      onChange={e => { setActivePreset(''); setConfig(c => ({ ...c, activation_rate: +e.target.value })) }}
                      style={css.slider} />
                    <p style={{ margin: '8px 0 0', fontSize: 12, color: '#94a3b8' }}>
                      Higher = more chaotic, faster-moving discussions.
                    </p>
                  </div>
                </div>
                </div>
              )}

              {optionsTab === 'research' && (
                <div>
                  <p style={{ fontSize: 13, color: '#64748b', margin: '0 0 16px' }}>
                    Configure how many results to fetch from each source. Set to 0 to skip a source.
                  </p>
                  <div className="options-grid" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                    {SOURCE_GROUPS.map(group => (
                      <div key={group.group} style={css.card}>
                        <div style={css.sectionTitle}>{group.group}</div>
                        {group.sources.map(src => (
                          <div key={src.key} style={{ marginBottom: 14 }}>
                            <div style={css.label}>
                              <div>
                                <div style={{ fontWeight: 500 }}>{src.label}</div>
                                <div style={{ fontSize: 11, color: '#94a3b8', marginTop: 1 }}>{src.description}</div>
                              </div>
                              <span style={css.value}>{config.source_limits[src.key] ?? src.defaultVal}</span>
                            </div>
                            <input type="range" min={0} max={src.max} step={5}
                              value={config.source_limits[src.key] ?? src.defaultVal}
                              onChange={e => setLimit(src.key, +e.target.value)}
                              style={css.slider} />
                          </div>
                        ))}
                      </div>
                    ))}
                  </div>
                  <button
                    onClick={() => setConfig(c => ({ ...c, source_limits: DEFAULT_SOURCE_LIMITS }))}
                    style={{
                      marginTop: 8, padding: '6px 14px', fontSize: 12,
                      border: '1px solid #e2e8f0', borderRadius: 6,
                      background: '#fff', color: '#64748b', cursor: 'pointer',
                    }}>
                    Reset to defaults
                  </button>
                </div>
              )}
            </div>
          )}
        </div>

        {error && (
          <p role="alert" style={{ color: '#ef4444', fontSize: 14, marginTop: 12, marginBottom: 0 }}>{error}</p>
        )}

        <button
          onClick={handleRun}
          disabled={loading}
          className={loading ? '' : 'run-btn'}
          style={{
            marginTop: 24, padding: '14px 36px', fontSize: 15, fontWeight: 700,
            background: loading ? '#94a3b8' : 'var(--primary)', color: '#fff',
            border: 'none', borderRadius: 10, cursor: loading ? 'not-allowed' : 'pointer',
            letterSpacing: '-0.01em', display: 'inline-flex', alignItems: 'center',
            animation: 'fadeInUp 0.6s ease both',
          }}>
          {loading && <span className="spinner" />}
          {loading ? 'Starting...' : 'Run Simulation →'}
        </button>

        {import.meta.env.VITE_CLERK_PUBLISHABLE_KEY && (
          <div style={{ marginTop: 10, fontSize: 11, color: '#94a3b8', display: 'flex', alignItems: 'center', gap: 5 }}>
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><rect x="2" y="4" width="20" height="16" rx="2"/><path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7"/></svg>
            <span>로그인 상태에서 시뮬레이션을 실행하면 완료 시 이메일로 보고서를 보내드립니다.</span>
          </div>
        )}
      </main>
    </div>
  )
}
