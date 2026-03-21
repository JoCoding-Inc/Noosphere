import { Link, useLocation } from 'react-router-dom'

export function Header() {
  const location = useLocation()
  const isHistory = location.pathname === '/history'

  return (
    <header style={{
      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      padding: '12px 28px',
      borderBottom: '1px solid #e2e8f0',
      background: '#fff',
    }}>
      <Link to="/" style={{ textDecoration: 'none', display: 'flex', alignItems: 'center', gap: 9 }}>
        <div style={{
          width: 26, height: 26, borderRadius: 7,
          background: 'linear-gradient(135deg, #6355e0, #8070ff)',
          boxShadow: '0 2px 8px rgba(99,85,224,0.28)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <div style={{
            width: 10, height: 10, borderRadius: '50%',
            border: '1.5px solid rgba(255,255,255,0.85)',
          }} />
        </div>
        <span style={{
          fontFamily: 'IBM Plex Mono, monospace',
          fontSize: 13, fontWeight: 500,
          color: '#1e293b', letterSpacing: '0.01em',
        }}>
          Noosphere
        </span>
      </Link>

      <nav style={{ display: 'flex', gap: 4 }}>
        <Link
          to="/history"
          style={{
            color: isHistory ? '#1e293b' : '#94a3b8',
            fontSize: 13,
            fontFamily: 'DM Sans, sans-serif',
            textDecoration: 'none',
            padding: '6px 12px',
            borderRadius: 6,
            fontWeight: isHistory ? 600 : 400,
            transition: 'color 0.15s, background 0.15s',
          }}
          onMouseEnter={e => {
            e.currentTarget.style.background = '#f8fafc'
            e.currentTarget.style.color = '#1e293b'
          }}
          onMouseLeave={e => {
            e.currentTarget.style.background = 'transparent'
            e.currentTarget.style.color = isHistory ? '#1e293b' : '#94a3b8'
          }}
        >
          History
        </Link>
      </nav>
    </header>
  )
}
