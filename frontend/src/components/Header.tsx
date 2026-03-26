import { useState } from 'react'
import { Link } from 'react-router-dom'
import { HistorySidebar } from './HistorySidebar'

export function Header() {
  const [historyOpen, setHistoryOpen] = useState(false)

  return (
    <>
      <header style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '12px 28px',
        borderBottom: '1px solid #e2e8f0',
        background: '#fff',
      }}>
        <Link to="/" style={{ textDecoration: 'none' }} />

        <nav style={{ display: 'flex', gap: 4 }}>
          <button
            onClick={() => setHistoryOpen(true)}
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
              transition: 'color 0.15s, background 0.15s',
            }}
            onMouseEnter={e => {
              e.currentTarget.style.background = '#f8fafc'
              e.currentTarget.style.color = '#1e293b'
            }}
            onMouseLeave={e => {
              e.currentTarget.style.background = 'transparent'
              e.currentTarget.style.color = '#94a3b8'
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
