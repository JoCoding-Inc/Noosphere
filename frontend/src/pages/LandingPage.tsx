import { Link } from 'react-router-dom'
import { LandingDemoWindow } from '../components/LandingDemoWindow'

const SIMULATION_PLATFORMS = [
  'Hacker News', 'Product Hunt', 'Indie Hackers', 'Reddit r/startups', 'LinkedIn',
]

const DATA_SOURCES = [
  'GitHub', 'arXiv', 'Semantic Scholar', 'Hacker News',
  'Reddit', 'Product Hunt', 'iTunes', 'Google Play', 'GDELT', 'Serper',
]

const STEPS = [
  {
    num: '01',
    title: 'Gather signals',
    desc: 'Real-world context sourced from GitHub, arXiv, Hacker News, Semantic Scholar, and more — to ground the simulation in truth.',
  },
  {
    num: '02',
    title: 'Generate personas',
    desc: 'AI personas constructed with distinct biases, expertise levels, and platform-native behavior. Researchers, skeptics, early adopters.',
  },
  {
    num: '03',
    title: 'Read the verdict',
    desc: 'Multi-round simulation produces a structured report — sentiment by segment, criticism clusters, and concrete improvement suggestions.',
  },
]

export function LandingPage() {
  return (
    <div style={{
      background: '#f8fafc',
      color: '#1e293b',
      minHeight: '100vh',
      fontFamily: "'DM Sans', sans-serif",
    }}>

      {/* ── Nav ──────────────────────────────────────────────────────── */}
      <nav className="landing-nav" style={{
        position: 'sticky', top: 0, zIndex: 10,
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '12px 28px',
          background: '#fff',
          borderBottom: '1px solid #e2e8f0',
        }}>
          <div />

      </nav>

      {/* ── Hero ─────────────────────────────────────────────────────── */}
      <section style={{
        display: 'flex', flexDirection: 'column', alignItems: 'center',
        textAlign: 'center',
        padding: '72px 24px 0',
        background: '#fff',
        borderBottom: '1px solid #f1f5f9',
      }}>
        <div style={{
          display: 'inline-flex', alignItems: 'center', gap: 7,
          padding: '4px 14px', borderRadius: 100,
          background: '#f1f5f9', border: '1px solid #e2e8f0',
          marginBottom: 22,
        }}>
          <div style={{ width: 6, height: 6, borderRadius: '50%', background: '#6355e0' }} />
          <span style={{
            fontFamily: "'IBM Plex Mono', monospace",
            fontSize: 10, letterSpacing: '0.1em',
            color: '#64748b', textTransform: 'uppercase' as const,
          }}>
            Pre-launch Intelligence
          </span>
        </div>

        <h1 className="landing-hero-h1" style={{
          fontFamily: "'Fraunces', serif",
          fontSize: 56, fontWeight: 600, lineHeight: 1.12,
          color: '#0f172a', margin: '0 0 18px',
          maxWidth: 680, letterSpacing: '-0.02em',
        }}>
          How will the market react{' '}
          <em style={{ fontStyle: 'italic', fontWeight: 300, color: '#94a3b8' }}>before</em>
          {' '}you launch?
        </h1>

        <p style={{
          fontSize: 17, lineHeight: 1.65, color: '#64748b',
          maxWidth: 500, margin: '0 0 36px',
        }}>
          Simulate real-world reactions across 5 tech communities — grounded in signals
          from GitHub, arXiv, Semantic Scholar, Hacker News, Reddit, Product Hunt, and more.
        </p>

        <div className="landing-hero-cta" style={{ display: 'flex', gap: 12, alignItems: 'center', marginBottom: 52 }}>
          <Link to="/app" style={{
            fontFamily: "'IBM Plex Mono', monospace",
            fontSize: 13, fontWeight: 500, color: '#fff',
            padding: '12px 26px', borderRadius: 9,
            background: '#1e293b', textDecoration: 'none',
            boxShadow: '0 2px 12px rgba(30,41,59,0.18)',
            transition: 'opacity 0.15s, transform 0.15s',
            display: 'inline-block',
          }}
            onMouseEnter={e => { e.currentTarget.style.opacity = '0.86'; e.currentTarget.style.transform = 'translateY(-1px)' }}
            onMouseLeave={e => { e.currentTarget.style.opacity = '1'; e.currentTarget.style.transform = 'translateY(0)' }}
          >
            Get Started →
          </Link>
          <a href="https://github.com/TaeyoungPark1005/Noosphere" target="_blank" rel="noopener noreferrer" style={{
            fontFamily: "'IBM Plex Mono', monospace",
            fontSize: 13, color: '#64748b',
            padding: '11px 26px', borderRadius: 9,
            border: '1.5px solid #e2e8f0', textDecoration: 'none',
            transition: 'border-color 0.15s, color 0.15s',
            display: 'inline-flex', alignItems: 'center', gap: 7,
          }}
            onMouseEnter={e => { e.currentTarget.style.borderColor = '#cbd5e1'; e.currentTarget.style.color = '#1e293b' }}
            onMouseLeave={e => { e.currentTarget.style.borderColor = '#e2e8f0'; e.currentTarget.style.color = '#64748b' }}
          >
            <svg width="15" height="15" viewBox="0 0 24 24" fill="currentColor"><path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0 0 24 12c0-6.63-5.37-12-12-12z"/></svg>
            GitHub
          </a>
        </div>

        {/* Auto-playing walkthrough window */}
        <div style={{ width: '100%', maxWidth: 900, marginBottom: 48, textAlign: 'left' }}>
          <LandingDemoWindow />
        </div>
      </section>

      {/* ── How it works ─────────────────────────────────────────────── */}
      <section id="how-it-works" style={{
        maxWidth: 860, margin: '0 auto', padding: '80px 24px',
      }}>
        <div style={{
          fontFamily: "'IBM Plex Mono', monospace",
          fontSize: 10, letterSpacing: '0.18em',
          color: '#94a3b8', textTransform: 'uppercase' as const,
          marginBottom: 32, textAlign: 'center',
        }}>
          How it works
        </div>

        <div style={{
          border: '1px solid #e2e8f0', borderRadius: 12,
          overflow: 'hidden', background: '#fff',
        }}>
          {STEPS.map((step, i) => (
            <div key={step.num} className="landing-how-row" style={{
              display: 'flex', alignItems: 'flex-start', gap: 28,
              padding: '28px 36px',
              borderBottom: i < STEPS.length - 1 ? '1px solid #f1f5f9' : 'none',
            }}>
              <span style={{
                fontFamily: "'IBM Plex Mono', monospace", fontSize: 12,
                color: '#94a3b8', letterSpacing: '0.06em',
                flexShrink: 0, paddingTop: 2, minWidth: 26,
              }}>
                {step.num}
              </span>
              <div className="landing-how-divider" style={{ width: 1, alignSelf: 'stretch', background: '#f1f5f9', flexShrink: 0 }} />
              <div className="landing-how-title" style={{ flexShrink: 0, minWidth: 160 }}>
                <span style={{
                  fontFamily: "'Fraunces', serif",
                  fontSize: 18, fontWeight: 600,
                  color: '#1e293b', lineHeight: 1.3,
                }}>
                  {step.title}
                </span>
              </div>
              <p style={{ fontSize: 14, lineHeight: 1.7, color: '#64748b', margin: 0, paddingTop: 2 }}>
                {step.desc}
              </p>
            </div>
          ))}
        </div>
      </section>

      {/* ── Platforms & Sources ───────────────────────────────────────── */}
      <section id="platforms" style={{
        maxWidth: 860, margin: '0 auto', padding: '0 24px 80px',
        textAlign: 'center',
      }}>
        <div style={{
          fontFamily: "'IBM Plex Mono', monospace",
          fontSize: 10, letterSpacing: '0.18em',
          color: '#94a3b8', textTransform: 'uppercase' as const,
          marginBottom: 14,
        }}>
          Simulation platforms
        </div>
        <div style={{ display: 'flex', flexWrap: 'wrap', justifyContent: 'center', gap: 8, marginBottom: 32 }}>
          {SIMULATION_PLATFORMS.map(name => (
            <span key={name} style={{
              fontFamily: "'IBM Plex Mono', monospace", fontSize: 11,
              color: '#475569', padding: '6px 14px',
              border: '1px solid #e2e8f0', borderRadius: 100,
              background: '#fff',
            }}>
              {name}
            </span>
          ))}
        </div>

        <div style={{
          fontFamily: "'IBM Plex Mono', monospace",
          fontSize: 10, letterSpacing: '0.18em',
          color: '#94a3b8', textTransform: 'uppercase' as const,
          marginBottom: 14,
        }}>
          Data sources
        </div>
        <div style={{ display: 'flex', flexWrap: 'wrap', justifyContent: 'center', gap: 8 }}>
          {DATA_SOURCES.map(name => (
            <span key={name} style={{
              fontFamily: "'IBM Plex Mono', monospace", fontSize: 11,
              color: '#94a3b8', padding: '5px 12px',
              border: '1px solid #f1f5f9', borderRadius: 100,
              background: '#f8fafc',
            }}>
              {name}
            </span>
          ))}
        </div>
      </section>

      {/* ── CTA ──────────────────────────────────────────────────────── */}
      <section style={{
        textAlign: 'center', padding: '72px 24px',
        background: '#fff', borderTop: '1px solid #e2e8f0',
      }}>
        <h2 style={{
          fontFamily: "'Fraunces', serif",
          fontSize: 42, fontWeight: 600, lineHeight: 1.15,
          color: '#0f172a', margin: '0 0 14px',
          letterSpacing: '-0.02em',
        }}>
          Launch with{' '}
          <em style={{ fontStyle: 'italic', fontWeight: 300, color: '#94a3b8' }}>informed</em>
          {' '}conviction.
        </h2>
        <p style={{ fontSize: 15, lineHeight: 1.65, color: '#64748b', margin: '0 0 32px' }}>
          Run your first simulation in under 2 minutes. No credit card required.
        </p>
        <Link to="/app" style={{
          fontFamily: "'IBM Plex Mono', monospace",
          fontSize: 13, fontWeight: 500, color: '#fff',
          padding: '13px 32px', borderRadius: 9,
          background: '#1e293b', textDecoration: 'none',
          boxShadow: '0 2px 12px rgba(30,41,59,0.18)',
          display: 'inline-block',
          transition: 'opacity 0.15s, transform 0.15s',
        }}
          onMouseEnter={e => { e.currentTarget.style.opacity = '0.86'; e.currentTarget.style.transform = 'translateY(-1px)' }}
          onMouseLeave={e => { e.currentTarget.style.opacity = '1'; e.currentTarget.style.transform = 'translateY(0)' }}
        >
          Get Started →
        </Link>
      </section>

      {/* ── Footer ───────────────────────────────────────────────────── */}
      <footer className="landing-footer" style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '20px 48px', borderTop: '1px solid #e2e8f0',
        background: '#f8fafc',
      }}>
        <span style={{
          fontFamily: "'IBM Plex Mono', monospace",
          fontSize: 12, color: '#94a3b8',
        }}>
          Noosphere
        </span>
        <span style={{
          fontFamily: "'IBM Plex Mono', monospace",
          fontSize: 11, color: '#cbd5e1',
        }}>
          © 2026 · Pre-launch Intelligence
        </span>
      </footer>
    </div>
  )
}
