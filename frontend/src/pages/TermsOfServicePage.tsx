// overrides/frontend/src/pages/TermsOfServicePage.tsx
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

export function TermsOfServicePage() {
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
            Terms of Service
          </h1>
          <p style={{ fontSize: t.font.size.lg, color: t.color.textMuted, margin: 0, fontFamily: "'IBM Plex Mono', monospace" }}>
            Last updated: March 28, 2026
          </p>
        </div>

        {/* 1. Acceptance */}
        <div style={SECTION_STYLE}>
          <h2 style={H2_STYLE}>1. Acceptance of Terms</h2>
          <p style={P_STYLE}>
            By accessing or using the Noosphere platform ("Service"), you agree to be
            bound by these Terms of Service ("Terms"). If you do not agree, do not use
            the Service.
          </p>
          <p style={P_STYLE}>
            We reserve the right to update these Terms at any time. Continued use of the
            Service after changes constitutes acceptance of the revised Terms.
          </p>
        </div>

        {/* 2. Description of Service */}
        <div style={SECTION_STYLE}>
          <h2 style={H2_STYLE}>2. Description of Service</h2>
          <p style={P_STYLE}>
            Noosphere is a market intelligence platform that simulates how your product
            idea might be received across technology communities — including Hacker News,
            Product Hunt, Indie Hackers, Reddit r/startups, and LinkedIn. The Service is
            designed to be useful at any stage: whether you are validating an idea before
            writing a single line of code, or stress-testing positioning before launch.
          </p>
          <p style={P_STYLE}>
            Simulations are AI-generated and draw on publicly available data from GitHub,
            arXiv, Semantic Scholar, Hacker News, Reddit, Product Hunt, Google Play,
            iTunes, GDELT, and web search results. The Service produces structured
            reports, persona-based discussion threads, ontology graphs, and go-to-market
            recommendations.
          </p>
        </div>

        {/* 3. Accounts */}
        <div style={SECTION_STYLE}>
          <h2 style={H2_STYLE}>3. Accounts and Authentication</h2>
          <p style={P_STYLE}>
            You must create an account to use the Service. Account creation requires a
            valid email address. We authenticate users via one-time password (OTP) emails;
            you are responsible for maintaining access to your email account.
          </p>
          <p style={P_STYLE}>
            You are responsible for all activity that occurs under your account. Notify us
            immediately at <a href="mailto:mu07010@jocoding.net" style={{ color: t.color.primaryVivid, textDecoration: 'none' }}>mu07010@jocoding.net</a> if you believe your account has been compromised.
          </p>
        </div>

        {/* 4. Credits and Payments */}
        <div style={SECTION_STYLE}>
          <h2 style={H2_STYLE}>4. Credits and Payments</h2>

          <p style={{ ...P_STYLE, fontWeight: 600, color: t.color.textPrimary }}>4.1 Credit System</p>
          <p style={P_STYLE}>
            The Service operates on a prepaid credit system. Credits are purchased in
            packages and consumed when you run simulations. Credit costs vary based on
            simulation configuration (number of rounds, platforms, agents, and data
            source limits).
          </p>

          <p style={{ ...P_STYLE, fontWeight: 600, color: t.color.textPrimary }}>4.2 Pricing</p>
          <div style={{
            border: `1px solid ${t.color.border}`,
            borderRadius: 10,
            overflow: 'hidden',
            marginBottom: 12,
          }}>
            {[
              { pkg: '65 credits', price: '$5.00 USD' },
              { pkg: '260 credits', price: '$20.00 USD' },
              { pkg: '650 credits', price: '$50.00 USD' },
            ].map((row, i, arr) => (
              <div key={row.pkg} style={{
                display: 'flex',
                justifyContent: 'space-between',
                padding: `${t.space[3]} 20px`,
                borderBottom: i < arr.length - 1 ? `1px solid ${t.color.bgSubtle}` : 'none',
                background: t.color.bgPage,
              }}>
                <span style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: t.font.size.md, color: t.color.textPrimary }}>{row.pkg}</span>
                <span style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: t.font.size.md, color: t.color.textSecondary }}>{row.price}</span>
              </div>
            ))}
          </div>
          <p style={P_STYLE}>
            Prices are in USD and may be subject to applicable taxes. We reserve the
            right to change prices at any time with notice.
          </p>

          <p style={{ ...P_STYLE, fontWeight: 600, color: t.color.textPrimary }}>4.3 No Refunds</p>
          <p style={P_STYLE}>
            All credit purchases are final and non-refundable. Credits consumed by
            completed or in-progress simulations cannot be restored. If a simulation
            fails due to a confirmed service-side error, we may issue a credit
            adjustment at our sole discretion.
          </p>

          <p style={{ ...P_STYLE, fontWeight: 600, color: t.color.textPrimary }}>4.4 Credit Expiration</p>
          <p style={P_STYLE}>
            Unused credits do not expire as long as your account remains active.
            Credits are forfeited upon account deletion.
          </p>
        </div>

        {/* 5. Acceptable Use */}
        <div style={SECTION_STYLE}>
          <h2 style={H2_STYLE}>5. Acceptable Use</h2>
          <p style={P_STYLE}>You agree not to use the Service to:</p>
          <ul style={UL_STYLE}>
            <li>Submit content that is unlawful, harmful, harassing, or fraudulent</li>
            <li>Attempt to reverse-engineer, scrape, or extract our AI models or system prompts</li>
            <li>Resell, redistribute, or sublicense access to the Service without our consent</li>
            <li>Use the Service to generate disinformation or content intended to deceive the public</li>
            <li>Circumvent rate limits, quotas, or authentication mechanisms</li>
            <li>Interfere with or disrupt the integrity or performance of the Service</li>
          </ul>
          <p style={P_STYLE}>
            We reserve the right to suspend or terminate accounts that violate these
            restrictions without prior notice.
          </p>
        </div>

        {/* 6. AI-Generated Content */}
        <div style={SECTION_STYLE}>
          <h2 style={H2_STYLE}>6. AI-Generated Content and Disclaimers</h2>
          <p style={P_STYLE}>
            All simulation outputs — including persona comments, sentiment verdicts,
            ontology graphs, and go-to-market recommendations — are generated by
            artificial intelligence models. These outputs are speculative and
            probabilistic in nature.
          </p>
          <p style={P_STYLE}>
            Noosphere does not guarantee the accuracy, completeness, or fitness for any
            particular purpose of simulation results. Outputs should be treated as one
            input among many when making business decisions, not as a substitute for
            professional market research, legal advice, or financial analysis.
          </p>
          <p style={P_STYLE}>
            The personas generated in simulations are entirely fictional. Any resemblance
            to real persons, living or dead, is coincidental.
          </p>
        </div>

        {/* 7. Intellectual Property */}
        <div style={SECTION_STYLE}>
          <h2 style={H2_STYLE}>7. Intellectual Property</h2>

          <p style={{ ...P_STYLE, fontWeight: 600, color: t.color.textPrimary }}>7.1 Your Content</p>
          <p style={P_STYLE}>
            You retain ownership of the idea descriptions and inputs you submit to the
            Service. By submitting content, you grant us a limited license to process
            it solely to provide the Service.
          </p>

          <p style={{ ...P_STYLE, fontWeight: 600, color: t.color.textPrimary }}>7.2 Our Service</p>
          <p style={P_STYLE}>
            The Noosphere platform, including its software, UI, models, and branding, is
            owned by us and protected by intellectual property laws. You may not copy,
            modify, or distribute any part of the Service without our express written
            permission.
          </p>

          <p style={{ ...P_STYLE, fontWeight: 600, color: t.color.textPrimary }}>7.3 Simulation Outputs</p>
          <p style={P_STYLE}>
            Simulation reports and outputs generated from your inputs are yours to use
            for personal and commercial purposes. You may not represent AI-generated
            outputs as independently produced market research.
          </p>
        </div>

        {/* 8. Privacy */}
        <div style={SECTION_STYLE}>
          <h2 style={H2_STYLE}>8. Privacy</h2>
          <p style={P_STYLE}>
            Your use of the Service is governed by our{' '}
            <Link to="/privacy" style={{ color: t.color.primaryVivid, textDecoration: 'none' }}>Privacy Policy</Link>,
            which is incorporated into these Terms by reference.
          </p>
        </div>

        {/* 9. Limitation of Liability */}
        <div style={SECTION_STYLE}>
          <h2 style={H2_STYLE}>9. Limitation of Liability</h2>
          <p style={P_STYLE}>
            To the maximum extent permitted by applicable law, Noosphere and its
            operators shall not be liable for any indirect, incidental, special,
            consequential, or punitive damages — including loss of profits, data,
            goodwill, or business opportunities — arising from your use of the Service,
            even if advised of the possibility of such damages.
          </p>
          <p style={P_STYLE}>
            Our total liability for any claim arising out of or relating to these Terms
            or the Service shall not exceed the amount you paid us in the twelve (12)
            months preceding the claim.
          </p>
        </div>

        {/* 10. Disclaimer of Warranties */}
        <div style={SECTION_STYLE}>
          <h2 style={H2_STYLE}>10. Disclaimer of Warranties</h2>
          <p style={P_STYLE}>
            The Service is provided "as is" and "as available" without warranties of any
            kind, express or implied, including but not limited to warranties of
            merchantability, fitness for a particular purpose, and non-infringement. We
            do not warrant that the Service will be uninterrupted, error-free, or free
            of viruses or other harmful components.
          </p>
        </div>

        {/* 11. Termination */}
        <div style={SECTION_STYLE}>
          <h2 style={H2_STYLE}>11. Termination</h2>
          <p style={P_STYLE}>
            You may close your account at any time by contacting us. We reserve the
            right to suspend or terminate your account immediately for violations of
            these Terms or for any other reason at our sole discretion.
          </p>
          <p style={P_STYLE}>
            Upon termination, your right to access the Service ceases immediately.
            Unused credits are forfeited and are not refundable upon termination for
            cause.
          </p>
        </div>

        {/* 12. Governing Law */}
        <div style={SECTION_STYLE}>
          <h2 style={H2_STYLE}>12. Governing Law</h2>
          <p style={P_STYLE}>
            These Terms shall be governed by and construed in accordance with applicable
            law. Any disputes shall be resolved through good-faith negotiation first,
            followed by binding arbitration if negotiation fails.
          </p>
        </div>

        {/* 13. Contact */}
        <div style={SECTION_STYLE}>
          <h2 style={H2_STYLE}>13. Contact Us</h2>
          <p style={P_STYLE}>
            For questions about these Terms, please contact us at:
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
