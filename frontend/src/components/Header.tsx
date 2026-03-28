import { useState } from 'react'
import { Link } from 'react-router-dom'
import { AppLogo } from './AppLogo'
import { HistorySidebar } from './HistorySidebar'

export function Header() {
  const [historyOpen, setHistoryOpen] = useState(false)

  return (
    <>
      <header style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '12px 28px',
        borderBottom: '1px solid #e2e8f0',
        background: 'rgba(255,255,255,0.85)',
        backdropFilter: 'blur(12px)',
        WebkitBackdropFilter: 'blur(12px)',
        position: 'sticky' as const,
        top: 0,
        zIndex: 50,
      }}>
        <Link to="/" style={{ textDecoration: 'none', display: 'flex', alignItems: 'center', gap: 9 }}>
          <AppLogo size={24} />
          <span style={{ fontFamily: 'IBM Plex Mono, monospace', fontSize: 13, fontWeight: 500, color: '#1e293b', letterSpacing: '0.01em' }}>
            Noosphere
          </span>
        </Link>

        <nav style={{ display: 'flex', gap: 4 }}>
          <button
            onClick={() => setHistoryOpen(true)}
            className="header-nav-btn"
            style={{
              color: '#94a3b8',
              fontSize: 13,
              fontFamily: 'DM Sans, sans-serif',
              textDecoration: 'none',
              padding: '6px 12px',
              borderRadius: 6,
              fontWeight: 400,
              background: 'none',
              border: 'none',
              cursor: 'pointer',
            }}
          >
            History
          </button>
        </nav>
      </header>

      <HistorySidebar open={historyOpen} onClose={() => setHistoryOpen(false)} />
    </>
  )
}
