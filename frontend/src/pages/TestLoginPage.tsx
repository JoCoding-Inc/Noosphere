// overrides/frontend/src/pages/TestLoginPage.tsx
import { useState, type FormEvent } from 'react'
import { t } from '../tokens'

export function TestLoginPage() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [status, setStatus] = useState<'idle' | 'loading' | 'error'>('idle')
  const [errorMsg, setErrorMsg] = useState('')

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setStatus('loading')
    setErrorMsg('')
    try {
      const res = await fetch('/test-login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      })
      const data = await res.json()
      if (!res.ok) {
        throw new Error(data.detail || `Error ${res.status}`)
      }
      if (data.url) {
        window.location.href = data.url
      } else {
        throw new Error('No URL in response')
      }
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : 'Unknown error')
      setStatus('error')
    }
  }

  return (
    <div style={{
      minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center',
      background: t.color.bgCard, fontFamily: "'DM Sans', sans-serif",
    }}>
      <form onSubmit={handleSubmit} style={{
        background: t.color.bgPage, border: `1px solid ${t.color.border}`, borderRadius: t.radius.lg,
        padding: '40px 36px', width: 340, display: 'flex', flexDirection: 'column', gap: t.space[4],
        boxShadow: '0 2px 16px rgba(15,23,42,0.07)',
      }}>
        <div style={{ marginBottom: t.space[2] }}>
          <div style={{
            fontFamily: "'IBM Plex Mono', monospace", fontSize: 10,
            letterSpacing: '0.12em', color: t.color.textMuted, textTransform: 'uppercase',
            marginBottom: t.space[2],
          }}>
            Test Access
          </div>
          <div style={{ fontSize: t.font.size['2xl'], fontWeight: t.font.weight.semibold, color: t.color.bgDark }}>
            Sign in to Noosphere
          </div>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          <label style={{ fontSize: t.font.size.sm, color: t.color.textSecondary, fontWeight: t.font.weight.medium }}>Email</label>
          <input
            type="email"
            value={email}
            onChange={e => setEmail(e.target.value)}
            required
            placeholder="Email"
            style={{
              padding: '9px 12px', borderRadius: 7, border: `1.5px solid ${t.color.border}`,
              fontSize: t.font.size.md, outline: 'none', color: t.color.textPrimary,
              fontFamily: "'IBM Plex Mono', monospace",
            }}
          />
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          <label style={{ fontSize: t.font.size.sm, color: t.color.textSecondary, fontWeight: t.font.weight.medium }}>Password</label>
          <input
            type="password"
            value={password}
            onChange={e => setPassword(e.target.value)}
            required
            style={{
              padding: '9px 12px', borderRadius: 7, border: `1.5px solid ${t.color.border}`,
              fontSize: t.font.size.md, outline: 'none', color: t.color.textPrimary,
              fontFamily: "'IBM Plex Mono', monospace",
            }}
          />
        </div>

        {status === 'error' && (
          <div style={{ fontSize: t.font.size.sm, color: t.color.danger, padding: `${t.space[2]} ${t.space[3]}`, background: t.color.dangerLight, borderRadius: t.radius.sm }}>
            {errorMsg}
          </div>
        )}

        <button
          type="submit"
          disabled={status === 'loading'}
          style={{
            marginTop: t.space[1], padding: '11px', borderRadius: t.radius.md,
            background: status === 'loading' ? t.color.textMuted : t.color.textPrimary,
            color: t.color.textInverse, border: 'none', fontSize: t.font.size.md, fontWeight: t.font.weight.medium,
            cursor: status === 'loading' ? 'not-allowed' : 'pointer',
            fontFamily: "'IBM Plex Mono', monospace", letterSpacing: '0.04em',
          }}
        >
          {status === 'loading' ? 'Signing in…' : 'Sign in →'}
        </button>
      </form>
    </div>
  )
}
