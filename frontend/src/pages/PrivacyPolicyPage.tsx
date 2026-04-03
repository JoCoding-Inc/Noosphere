// overrides/frontend/src/pages/PrivacyPolicyPage.tsx
import { Link } from 'react-router-dom'
import { t } from '../tokens'

const SECTION_STYLE: React.CSSProperties = {
  marginBottom: 40,
}

const H2_STYLE: React.CSSProperties = {
  fontFamily: "'Fraunces', serif",
  fontSize: 22,
  fontWeight: 600,
  color: t.color.bgDark,
  margin: '0 0 12px',
  letterSpacing: '-0.01em',
}

const P_STYLE: React.CSSProperties = {
  fontSize: 14,
  lineHeight: 1.8,
  color: t.color.textStrong,
  margin: '0 0 12px',
}

const UL_STYLE: React.CSSProperties = {
  fontSize: 14,
  lineHeight: 1.8,
  color: t.color.textStrong,
  margin: '0 0 12px',
  paddingLeft: 24,
}

export function PrivacyPolicyPage() {
  return (
    <div style={{
      background: t.color.bgCard,
      minHeight: '100vh',
      fontFamily: "'DM Sans', sans-serif",
    }}>
      {/* Nav */}
      <div style={{
        borderBottom: `1px solid ${t.color.border}`,
        background: t.color.bgPage,
        padding: '14px 48px',
        display: 'flex',
        alignItems: 'center',
      }}>
        <Link to="/" style={{
          fontFamily: "'IBM Plex Mono', monospace",
          fontSize: t.font.size.md,
          color: t.color.textSecondary,
          textDecoration: 'none',
        }}>
          ← Noosphere
        </Link>
      </div>

      <div style={{
        maxWidth: 760,
        margin: '0 auto',
        padding: '64px 24px 96px',
      }}>
        {/* Header */}
        <div style={{ marginBottom: 56 }}>
          <div style={{
            fontFamily: "'IBM Plex Mono', monospace",
            fontSize: 10,
            letterSpacing: '0.18em',
            color: t.color.textMuted,
            textTransform: 'uppercase',
            marginBottom: 14,
          }}>
            Legal
          </div>
          <h1 style={{
            fontFamily: "'Fraunces', serif",
            fontSize: 42,
            fontWeight: 600,
            color: t.color.bgDark,
            margin: '0 0 14px',
            letterSpacing: '-0.02em',
          }}>
            Privacy Policy
          </h1>
          <p style={{ fontSize: t.font.size.lg, color: t.color.textMuted, margin: 0, fontFamily: "'IBM Plex Mono', monospace" }}>
            Last updated: March 28, 2026
          </p>
        </div>

        {/* 1. Introduction */}
        <div style={SECTION_STYLE}>
          <h2 style={H2_STYLE}>1. Introduction</h2>
          <p style={P_STYLE}>
            Noosphere ("we," "us," or "our") operates the Noosphere market intelligence
            platform, accessible at this website (the "Service"). This Privacy Policy explains
            what information we collect, how we use it, and the choices you have with respect
            to that information.
          </p>
          <p style={P_STYLE}>
            By using the Service, you agree to the collection and use of information in
            accordance with this policy.
          </p>
        </div>

        {/* 2. Information We Collect */}
        <div style={SECTION_STYLE}>
          <h2 style={H2_STYLE}>2. Information We Collect</h2>

          <p style={{ ...P_STYLE, fontWeight: 600, color: t.color.textPrimary }}>2.1 Account Information</p>
          <p style={P_STYLE}>
            When you create an account, we collect your email address through our
            authentication provider (Clerk). We use a one-time password (OTP) flow —
            no passwords are stored by us.
          </p>

          <p style={{ ...P_STYLE, fontWeight: 600, color: t.color.textPrimary }}>2.2 Usage Data</p>
          <p style={P_STYLE}>We automatically collect information about how you interact with the Service, including:</p>
          <ul style={UL_STYLE}>
            <li>Simulation inputs (the idea or product description you submit)</li>
            <li>Simulation results and history</li>
            <li>Pages visited, features used, and time spent</li>
            <li>IP address, browser type, and device information</li>
          </ul>

          <p style={{ ...P_STYLE, fontWeight: 600, color: t.color.textPrimary }}>2.3 Payment Information</p>
          <p style={P_STYLE}>
            Credit purchases are processed by Stripe. We do not store your full card
            number, CVV, or billing address. We receive and store only transaction
            metadata (amount, credit package, timestamp) necessary for credit accounting.
          </p>
        </div>

        {/* 3. How We Use Your Information */}
        <div style={SECTION_STYLE}>
          <h2 style={H2_STYLE}>3. How We Use Your Information</h2>
          <ul style={UL_STYLE}>
            <li>To provide, operate, and improve the Service</li>
            <li>To process credit purchases and maintain your credit balance</li>
            <li>To send transactional emails (OTP login codes, purchase receipts)</li>
            <li>To analyze usage patterns and improve our simulation models</li>
            <li>To detect and prevent fraud or misuse</li>
            <li>To comply with legal obligations</li>
          </ul>
        </div>

        {/* 4. Third-Party Services */}
        <div style={SECTION_STYLE}>
          <h2 style={H2_STYLE}>4. Third-Party Services</h2>
          <p style={P_STYLE}>We use the following third-party services, each governed by their own privacy policies:</p>

          <div style={{
            border: `1px solid ${t.color.border}`,
            borderRadius: 10,
            overflow: 'hidden',
            marginBottom: 12,
          }}>
            {[
              { name: 'Clerk', purpose: 'User authentication and session management' },
              { name: 'Stripe', purpose: 'Payment processing for credit purchases' },
              { name: 'Resend', purpose: 'Transactional email delivery (OTP, receipts)' },
              { name: 'Google Analytics (GA4)', purpose: 'Website analytics and usage statistics' },
              { name: 'Microsoft Clarity', purpose: 'Session recording and heatmaps for UX improvement' },
              { name: 'PostHog', purpose: 'Product analytics and funnel analysis' },
              { name: 'OpenAI', purpose: 'AI model inference for simulation and persona generation' },
            ].map((svc, i, arr) => (
              <div key={svc.name} style={{
                display: 'flex',
                gap: 16,
                padding: `${t.space[3]} 20px`,
                borderBottom: i < arr.length - 1 ? `1px solid ${t.color.bgSubtle}` : 'none',
                background: t.color.bgPage,
                alignItems: 'flex-start',
              }}>
                <span style={{
                  fontFamily: "'IBM Plex Mono', monospace",
                  fontSize: t.font.size.sm,
                  color: t.color.textPrimary,
                  minWidth: 180,
                  flexShrink: 0,
                }}>
                  {svc.name}
                </span>
                <span style={{ fontSize: t.font.size.md, color: t.color.textSecondary, lineHeight: 1.5 }}>
                  {svc.purpose}
                </span>
              </div>
            ))}
          </div>

          <p style={P_STYLE}>
            These services may collect and process data independently. We encourage you to
            review their respective privacy policies.
          </p>
        </div>

        {/* 5. Data Sources Used for Simulations */}
        <div style={SECTION_STYLE}>
          <h2 style={H2_STYLE}>5. Data Sources Used for Simulations</h2>
          <p style={P_STYLE}>
            To ground simulations in real-world context, the Service fetches publicly
            available data from the following sources at the time of each simulation:
          </p>
          <ul style={UL_STYLE}>
            <li>GitHub (public repositories and activity)</li>
            <li>arXiv and Semantic Scholar (academic publications)</li>
            <li>Hacker News, Reddit, Product Hunt (public discussions)</li>
            <li>iTunes and Google Play (app store listings)</li>
            <li>GDELT (global news events)</li>
            <li>Web search results via Serper</li>
          </ul>
          <p style={P_STYLE}>
            This data is retrieved transiently and used solely to generate simulation
            context. It is not sold or shared with third parties beyond what is necessary
            to run the Service.
          </p>
        </div>

        {/* 6. Cookies and Tracking */}
        <div style={SECTION_STYLE}>
          <h2 style={H2_STYLE}>6. Cookies and Tracking Technologies</h2>
          <p style={P_STYLE}>
            We use cookies and similar tracking technologies to maintain your session,
            remember your preferences, and understand how you use the Service. Analytics
            providers (GA4, Clarity, PostHog) may set their own cookies.
          </p>
          <p style={P_STYLE}>
            You can control cookies through your browser settings. Disabling cookies may
            affect Service functionality.
          </p>
        </div>

        {/* 7. Data Retention */}
        <div style={SECTION_STYLE}>
          <h2 style={H2_STYLE}>7. Data Retention</h2>
          <p style={P_STYLE}>
            We retain your account data and simulation history for as long as your account
            is active. If you request account deletion, we will delete your personal data
            within 30 days, except where retention is required by law or for fraud
            prevention purposes.
          </p>
        </div>

        {/* 8. Your Rights */}
        <div style={SECTION_STYLE}>
          <h2 style={H2_STYLE}>8. Your Rights</h2>
          <p style={P_STYLE}>Depending on your location, you may have the following rights:</p>
          <ul style={UL_STYLE}>
            <li>Access the personal data we hold about you</li>
            <li>Request correction of inaccurate data</li>
            <li>Request deletion of your account and associated data</li>
            <li>Object to or restrict certain processing activities</li>
            <li>Data portability (export your simulation history)</li>
          </ul>
          <p style={P_STYLE}>
            To exercise these rights, contact us at the email address below.
          </p>
        </div>

        {/* 9. Children's Privacy */}
        <div style={SECTION_STYLE}>
          <h2 style={H2_STYLE}>9. Children's Privacy</h2>
          <p style={P_STYLE}>
            The Service is not directed to individuals under the age of 16. We do not
            knowingly collect personal information from children. If you believe a child
            has provided us with personal data, please contact us and we will delete it.
          </p>
        </div>

        {/* 10. Changes */}
        <div style={SECTION_STYLE}>
          <h2 style={H2_STYLE}>10. Changes to This Policy</h2>
          <p style={P_STYLE}>
            We may update this Privacy Policy from time to time. We will notify you of
            material changes by updating the "Last updated" date at the top of this page.
            Continued use of the Service after changes constitutes acceptance of the
            updated policy.
          </p>
        </div>

        {/* 11. Contact */}
        <div style={SECTION_STYLE}>
          <h2 style={H2_STYLE}>11. Contact Us</h2>
          <p style={P_STYLE}>
            If you have questions or concerns about this Privacy Policy, please contact us at:
          </p>
          <p style={{ ...P_STYLE, margin: 0 }}>
            <a href="mailto:mu07010@jocoding.net" style={{ color: t.color.primaryVivid, textDecoration: 'none' }}>mu07010@jocoding.net</a>
            <br />
            Jocoding.Inc<br />
            1111B S Governors Ave, STE 80543<br />
            Dover, Delaware 19904, USA
          </p>
        </div>
      </div>

      {/* Footer */}
      <footer style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: `${t.space[5]} 48px`,
        borderTop: `1px solid ${t.color.border}`,
        background: t.color.bgCard,
      }}>
        <span style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: t.font.size.sm, color: t.color.textMuted }}>Noosphere</span>
        <div style={{ display: 'flex', gap: 20, alignItems: 'center' }}>
          <Link to="/privacy" style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: t.font.size.xs, color: t.color.textMuted, textDecoration: 'none' }}>Privacy Policy</Link>
          <Link to="/terms" style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: t.font.size.xs, color: t.color.textMuted, textDecoration: 'none' }}>Terms of Service</Link>
          <span style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: t.font.size.xs, color: '#cbd5e1' }}>© 2026 Jocoding.Inc · Market Intelligence</span>
        </div>
      </footer>
    </div>
  )
}
