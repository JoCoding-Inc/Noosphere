import { Link } from 'react-router-dom'
import { t } from '../tokens'
import { AppLogo } from '../components/AppLogo'

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
      background: t.color.bgCard,
      color: t.color.textPrimary,
      minHeight: '100vh',
      fontFamily: "'DM Sans', sans-serif",
    }}>

      {/* ── Nav ──────────────────────────────────────────────────────── */}
      <nav className="landing-nav" style={{
        position: 'sticky', top: 0, zIndex: 10,
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '12px 28px',
          background: t.color.bgPage,
          borderBottom: `1px solid ${t.color.border}`,
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 9 }}>
            <AppLogo size={24} />
            <span style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: t.font.size.md, fontWeight: t.font.weight.medium, color: t.color.textPrimary }}>
              Noosphere
            </span>
          </div>

      </nav>

      {/* ── Hero ─────────────────────────────────────────────────────── */}
      <section style={{
        display: 'flex', flexDirection: 'column', alignItems: 'center',
        textAlign: 'center',
        padding: '72px 24px 0',
        background: t.color.bgPage,
        borderBottom: `1px solid ${t.color.bgSubtle}`,
        position: 'relative',
      }}>
        {/* gradient accent */}
        <div style={{
          position: 'absolute', top: 0, left: 0, right: 0, height: 3,
          background: 'linear-gradient(90deg, #6366f1, #818cf8, #a5b4fc)',
          borderRadius: '0 0 2px 2px',
        }} />
        <div style={{
          display: 'inline-flex', alignItems: 'center', gap: 7,
          padding: '4px 14px', borderRadius: 100,
          background: t.color.bgSubtle, border: `1px solid ${t.color.border}`,
          marginBottom: 22,
        }}>
          <div style={{ width: 6, height: 6, borderRadius: '50%', background: t.color.primaryVivid }} />
          <span style={{
            fontFamily: "'IBM Plex Mono', monospace",
            fontSize: 10, letterSpacing: '0.1em',
            color: t.color.textSecondary, textTransform: 'uppercase' as const,
          }}>
            Pre-launch Intelligence
          </span>
        </div>

        <h1 className="landing-hero-h1" style={{
          fontFamily: "'Fraunces', serif",
          fontSize: 56, fontWeight: t.font.weight.semibold, lineHeight: 1.12,
          color: t.color.bgDark, margin: '0 0 18px',
          maxWidth: 680, letterSpacing: '-0.02em',
        }}>
          How will the market react{' '}
          <em style={{ fontStyle: 'italic', fontWeight: 300, color: t.color.textMuted }}>before</em>
          {' '}you launch?
        </h1>

        <p style={{
          fontSize: 17, lineHeight: 1.65, color: t.color.textSecondary,
          maxWidth: 500, margin: '0 0 36px',
        }}>
          Simulate real-world reactions across 5 tech communities — grounded in signals
          from GitHub, arXiv, Semantic Scholar, Hacker News, Reddit, Product Hunt, and more.
        </p>

        <div className="landing-hero-cta" style={{ display: 'flex', gap: 12, alignItems: 'center', marginBottom: 52 }}>
          <Link to="/app" className="landing-cta-primary" style={{
            fontFamily: "'IBM Plex Mono', monospace",
            fontSize: t.font.size.md, fontWeight: t.font.weight.medium, color: t.color.textInverse,
            padding: '12px 26px', borderRadius: 9,
            background: 'var(--primary)', textDecoration: 'none',
            boxShadow: '0 2px 12px rgba(99,102,241,0.3)',
            display: 'inline-block',
          }}
          >
            Get Started →
          </Link>
          <a href="https://github.com/TaeyoungPark1005/Noosphere" target="_blank" rel="noopener noreferrer" className="landing-cta-secondary" style={{
            fontFamily: "'IBM Plex Mono', monospace",
            fontSize: t.font.size.md, color: t.color.textSecondary,
            padding: '11px 26px', borderRadius: 9,
            border: `1.5px solid ${t.color.border}`, textDecoration: 'none',
            display: 'inline-flex', alignItems: 'center', gap: 7,
          }}
          >
            <svg width="15" height="15" viewBox="0 0 24 24" fill="currentColor"><path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0 0 24 12c0-6.63-5.37-12-12-12z"/></svg>
            GitHub
          </a>
        </div>

        {/* Demo video */}
        <div style={{ width: '100%', maxWidth: 900, marginBottom: 48 }}>
          <div style={{
            position: 'relative', paddingBottom: '56.25%', height: 0,
            borderRadius: 14, overflow: 'hidden',
            boxShadow: '0 4px 32px rgba(15,23,42,0.10)',
            border: `1px solid ${t.color.border}`,
          }}>
            <iframe
              src="https://www.youtube.com/embed/WPQOuvVJQXM?autoplay=0&rel=0&modestbranding=1"
              title="Noosphere Demo"
              allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
              allowFullScreen
              style={{
                position: 'absolute', top: 0, left: 0,
                width: '100%', height: '100%',
                border: 'none',
              }}
            />
          </div>
        </div>
      </section>

      {/* ── How it works ─────────────────────────────────────────────── */}
      <section id="how-it-works" style={{
        maxWidth: 860, margin: '0 auto', padding: '80px 24px',
      }}>
        <div style={{
          fontFamily: "'IBM Plex Mono', monospace",
          fontSize: 10, letterSpacing: '0.18em',
          color: t.color.textMuted, textTransform: 'uppercase' as const,
          marginBottom: 32, textAlign: 'center',
        }}>
          How it works
        </div>

        <div style={{
          border: `1px solid ${t.color.border}`, borderRadius: t.radius.lg,
          overflow: 'hidden', background: t.color.bgPage,
          boxShadow: 'var(--shadow-card)',
        }}>
          {STEPS.map((step, i) => (
            <div key={step.num} className="landing-how-row" style={{
              display: 'flex', alignItems: 'flex-start', gap: 28,
              padding: '28px 36px',
              borderBottom: i < STEPS.length - 1 ? `1px solid ${t.color.bgSubtle}` : 'none',
            }}>
              <span style={{
                fontFamily: "'IBM Plex Mono', monospace", fontSize: t.font.size.sm,
                color: t.color.textMuted, letterSpacing: '0.06em',
                flexShrink: 0, paddingTop: 2, minWidth: 26,
              }}>
                {step.num}
              </span>
              <div className="landing-how-divider" style={{ width: 1, alignSelf: 'stretch', background: t.color.bgSubtle, flexShrink: 0 }} />
              <div className="landing-how-title" style={{ flexShrink: 0, minWidth: 160 }}>
                <span style={{
                  fontFamily: "'Fraunces', serif",
                  fontSize: 18, fontWeight: t.font.weight.semibold,
                  color: t.color.textPrimary, lineHeight: 1.3,
                }}>
                  {step.title}
                </span>
              </div>
              <p style={{ fontSize: t.font.size.lg, lineHeight: 1.7, color: t.color.textSecondary, margin: 0, paddingTop: 2 }}>
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
          background: t.color.primarySurface,
          borderRadius: t.radius.xl,
          padding: '40px 24px',
          border: `1px solid ${t.color.primaryLight}`,
        }}>

        <div style={{
          fontFamily: "'IBM Plex Mono', monospace",
          fontSize: 10, letterSpacing: '0.18em',
          color: t.color.textMuted, textTransform: 'uppercase' as const,
          marginBottom: 14,
        }}>
          Simulation platforms
        </div>
        <div style={{ display: 'flex', flexWrap: 'wrap', justifyContent: 'center', gap: 8, marginBottom: 32 }}>
          {SIMULATION_PLATFORMS.map(name => (
            <span key={name} style={{
              fontFamily: "'IBM Plex Mono', monospace", fontSize: t.font.size.xs,
              color: t.color.textStrong, padding: '6px 14px',
              border: `1px solid ${t.color.border}`, borderRadius: 100,
              background: t.color.bgPage,
              transition: 'border-color 0.15s ease, background 0.15s ease',
            }}>
              {name}
            </span>
          ))}
        </div>

        <div style={{
          fontFamily: "'IBM Plex Mono', monospace",
          fontSize: 10, letterSpacing: '0.18em',
          color: t.color.textMuted, textTransform: 'uppercase' as const,
          marginBottom: 14,
        }}>
          Data sources
        </div>
        <div style={{ display: 'flex', flexWrap: 'wrap', justifyContent: 'center', gap: 8 }}>
          {DATA_SOURCES.map(name => (
            <span key={name} style={{
              fontFamily: "'IBM Plex Mono', monospace", fontSize: t.font.size.xs,
              color: t.color.textMuted, padding: '5px 12px',
              border: `1px solid ${t.color.bgSubtle}`, borderRadius: 100,
              background: t.color.bgCard,
            }}>
              {name}
            </span>
          ))}
        </div>
        </div>
      </section>

      {/* ── CTA ──────────────────────────────────────────────────────── */}
      <section style={{
        textAlign: 'center', padding: '72px 24px',
        background: t.color.bgPage, borderTop: `1px solid ${t.color.border}`,
      }}>
        <h2 style={{
          fontFamily: "'Fraunces', serif",
          fontSize: 42, fontWeight: t.font.weight.semibold, lineHeight: 1.15,
          color: t.color.bgDark, margin: '0 0 14px',
          letterSpacing: '-0.02em',
        }}>
          Launch with{' '}
          <em style={{ fontStyle: 'italic', fontWeight: 300, color: t.color.textMuted }}>informed</em>
          {' '}conviction.
        </h2>
        <p style={{ fontSize: 15, lineHeight: 1.65, color: t.color.textSecondary, margin: '0 0 32px' }}>
          Run your first simulation in under 2 minutes.
        </p>
        <Link to="/app" className="landing-cta-primary" style={{
          fontFamily: "'IBM Plex Mono', monospace",
          fontSize: t.font.size.md, fontWeight: t.font.weight.medium, color: t.color.textInverse,
          padding: '13px 32px', borderRadius: 9,
          background: 'var(--primary)', textDecoration: 'none',
          boxShadow: '0 2px 12px rgba(99,102,241,0.3)',
          display: 'inline-block',
        }}
        >
          Get Started →
        </Link>
      </section>

      {/* ── Footer ───────────────────────────────────────────────────── */}
      <footer className="landing-footer" style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '20px 48px', borderTop: `1px solid ${t.color.bgSubtle}`,
        background: t.color.bgPage,
      }}>
        <span style={{
          fontFamily: "'IBM Plex Mono', monospace",
          fontSize: t.font.size.sm, color: t.color.textMuted,
        }}>
          Noosphere
        </span>
        <span style={{
          fontFamily: "'IBM Plex Mono', monospace",
          fontSize: t.font.size.xs, color: t.color.borderLight,
        }}>
          © 2026 · Pre-launch Intelligence
        </span>
      </footer>
    </div>
  )
}
