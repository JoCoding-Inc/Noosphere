import type { ReportJSON } from '../types'
import { t } from '../tokens'
import { VERDICT_CONFIG } from '../constants'

const SENTIMENT_DOT: Record<string, string> = {
  positive: t.color.success,
  neutral:  t.color.textMuted,
  negative: t.color.danger,
}

export function ReportView({ report, noSummary, noDetails }: {
  report: ReportJSON | null | undefined
  noSummary?: boolean
  noDetails?: boolean
}) {
  if (!report || !report.verdict) {
    if (noSummary) return null
    return (
      <div style={{ padding: 48, textAlign: 'center', color: t.color.textMuted, fontSize: t.font.size.lg }}>
        <div style={{ marginBottom: t.space[3], display: 'flex', justifyContent: 'center' }}>
          <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke={t.color.textMuted} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/>
          </svg>
        </div>
        No simulation report available.
      </div>
    )
  }

  const v = VERDICT_CONFIG[report.verdict] || VERDICT_CONFIG.mixed
  const hasValidation = report.validation && report.validation.corrections_applied > 0

  const adoptionScore = report.adoption_score
  const adoptionColor = adoptionScore == null ? t.color.textMuted
    : adoptionScore <= 30 ? t.color.danger
    : adoptionScore <= 60 ? t.color.warning
    : adoptionScore <= 80 ? t.color.lime
    : t.color.success

  return (
    <div>
      {/* ── Summary section: verdict cards + alerts ── */}
      {!noSummary && (
        <>
          <div style={{ display: 'flex', gap: t.space[4], marginBottom: t.space[6], flexWrap: 'wrap' }}>
            <div style={{
              flex: 1, minWidth: 200,
              padding: t.space[5], borderRadius: t.radius.lg,
              border: `1px solid ${v.color}20`,
              background: `${v.color}08`,
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: t.space[2], marginBottom: t.space[1] }}>
                <svg
                  width="24" height="24" viewBox="0 0 24 24"
                  fill="none" stroke={v.color} strokeWidth="2"
                  aria-hidden="true"
                  style={{ flexShrink: 0 }}
                  dangerouslySetInnerHTML={{ __html: v.icon }}
                />
                <span style={{ fontSize: t.font.size['2xl'], fontWeight: t.font.weight.bold, color: v.color }}>{v.label}</span>
              </div>
              <p style={{ margin: 0, fontSize: t.font.size.lg, color: t.color.textSecondary }}>
                Based on {report.evidence_count} simulated interactions
              </p>
            </div>

            {adoptionScore != null && (
              <div style={{
                display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
                padding: t.space[5], borderRadius: t.radius.lg, minWidth: 140,
                border: `1px solid ${adoptionColor}20`,
                background: `${adoptionColor}08`,
              }}>
                <div style={{ position: 'relative', width: 72, height: 72, marginBottom: t.space[2] }}>
                  <svg width="72" height="72" viewBox="0 0 72 72" style={{ transform: 'rotate(-90deg)' }}>
                    <circle cx="36" cy="36" r="30" fill="none" stroke={t.color.border} strokeWidth="6" />
                    <circle
                      cx="36" cy="36" r="30" fill="none"
                      stroke={adoptionColor} strokeWidth="6"
                      strokeLinecap="round"
                      strokeDasharray={`${(adoptionScore / 100) * 188.5} 188.5`}
                    />
                  </svg>
                  <span style={{
                    position: 'absolute', inset: 0,
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    fontSize: t.font.size['2xl'], fontWeight: t.font.weight.bold, color: adoptionColor,
                  }}>
                    {adoptionScore}
                  </span>
                </div>
                <span style={{ fontSize: t.font.size.sm, fontWeight: t.font.weight.semibold, color: t.color.textSecondary }}>Adoption Score</span>
                <span style={{ fontSize: t.font.size.xs, color: t.color.textMuted }}>{adoptionScore} / 100</span>
              </div>
            )}

            {report.consensus_score !== undefined && (
              <div style={{
                display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
                padding: t.space[5], borderRadius: t.radius.lg, minWidth: 120,
                border: '1px solid #10b98120',
                background: '#10b98108',
              }}>
                <div style={{ fontSize: t.font.size.xs, color: t.color.textMuted, marginBottom: t.space[1] }}>Platform Consensus</div>
                <div style={{ fontSize: 22, fontWeight: t.font.weight.bold, color: t.color.successAlt }}>
                  {report.consensus_score}%
                </div>
              </div>
            )}

            {report.response_rate !== undefined && (
              <div style={{
                display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
                padding: t.space[5], borderRadius: t.radius.lg, minWidth: 120,
                border: '1px solid #3b82f620',
                background: '#3b82f608',
              }}>
                <div style={{ fontSize: t.font.size.xs, color: t.color.textMuted, marginBottom: t.space[1] }}>Response Rate</div>
                <div style={{ fontSize: 22, fontWeight: t.font.weight.bold, color: t.color.info }}>
                  {Math.round(report.response_rate * 100)}%
                </div>
              </div>
            )}
          </div>

          {hasValidation && (
            <div
              style={{
                display: 'inline-flex', alignItems: 'center', gap: t.space[1],
                background: t.color.warningLight, color: t.color.warningText,
                border: `1px solid ${t.color.warningBorder}`, borderRadius: t.radius.pill,
                fontSize: t.font.size.sm, fontWeight: t.font.weight.semibold, padding: '5px 12px',
                marginBottom: t.space[4], cursor: 'default',
              }}
              title={report.validation?.details?.join('\n') ?? ''}
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke={t.color.warning} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ flexShrink: 0 }} aria-hidden="true">
                <path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/>
                <line x1="12" y1="9" x2="12" y2="13"/>
                <line x1="12" y1="17" x2="12.01" y2="17"/>
              </svg>
              {report.validation?.corrections_applied} auto-corrections applied
            </div>
          )}

          {report.platform_divergence && report.platform_divergence.length > 0 && (
            <div style={{ background: '#1e1b4b22', border: `1px solid ${t.color.primary}`, borderRadius: t.radius.md, padding: t.space[3], marginBottom: t.space[3] }}>
              <div style={{ fontWeight: t.font.weight.semibold, color: t.color.primaryMuted, fontSize: t.font.size.md, marginBottom: t.space[1] }}>
                Platform Divergence Detected
              </div>
              {report.platform_divergence.map((d, i) => (
                <div key={i} style={{ color: t.color.textMuted, fontSize: t.font.size.sm }}>
                  {d.platform_a} vs {d.platform_b}: {d.gap_pct}%p gap — {d.direction}
                </div>
              ))}
            </div>
          )}

          {report.engagement_alerts && report.engagement_alerts.length > 0 && (
            <div style={{
              background: '#451a0322',
              border: `1px solid ${t.color.warning}`,
              borderRadius: t.radius.md,
              padding: t.space[3],
              marginBottom: t.space[6],
            }}>
              <div style={{ fontWeight: t.font.weight.semibold, color: t.color.warning, fontSize: t.font.size.md, marginBottom: t.space[1] }}>
                Engagement Drop Detected
              </div>
              {report.engagement_alerts.map((alert, i) => (
                <div key={i} style={{ color: t.color.textMuted, fontSize: t.font.size.sm }}>
                  Round {alert.round}: engagement dropped {alert.drop_pct}%
                  ({alert.prev_engagement} → {alert.curr_engagement})
                </div>
              ))}
            </div>
          )}
        </>
      )}

      {/* ── Details section: segment reactions + analysis ── */}
      {!noDetails && (
        <>
          <h3 style={{ fontSize: t.font.size.xl, fontWeight: t.font.weight.semibold, marginBottom: t.space[3] }}>Segment Reactions</h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12, marginBottom: 24 }}>
            {(report.segments || []).map(seg => (
              <div key={seg.name} style={{
                padding: 14, borderRadius: t.radius.md, border: `1px solid ${t.color.border}`, background: t.color.bgPage,
                boxShadow: 'var(--shadow-card)',
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                  <span style={{
                      width: 8, height: 8, borderRadius: '50%',
                      background: SENTIMENT_DOT[seg.sentiment] || '#94a3b8',
                      display: 'inline-block', flexShrink: 0,
                    }} />
                  <span style={{ fontWeight: t.font.weight.semibold, fontSize: t.font.size.lg }}>
                    {seg.name.replace('_', ' ').replace(/\b\w/g, c => c.toUpperCase())}
                  </span>
                </div>
                <p style={{ margin: '0 0 8px', fontSize: t.font.size.lg, color: t.color.textStrong }}>{seg.summary}</p>
                {(seg.key_quotes || []).map((q, i) => (
                  <p key={i} style={{
                    margin: '4px 0', paddingLeft: t.space[3], borderLeft: `3px solid ${t.color.border}`,
                    fontSize: t.font.size.md, color: t.color.textSecondary, fontStyle: 'italic',
                  }}>"{q}"</p>
                ))}
              </div>
            ))}
          </div>

          {(report.praise_clusters ?? []).length > 0 && (
            <>
              <h3 style={{ fontSize: t.font.size.xl, fontWeight: t.font.weight.semibold, marginBottom: t.space[3] }}>What Resonated</h3>
              <div style={{ display: 'flex', flexDirection: 'column', gap: t.space[2], marginBottom: t.space[6] }}>
                {report.praise_clusters!.map((c, i) => (
                  <div key={i} style={{
                    padding: t.space[3], borderRadius: t.radius.md, border: `1px solid ${t.color.successBorder}`,
                    background: t.color.successLight,
                    boxShadow: '0 1px 3px rgba(34,197,94,0.06)',
                  }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: t.space[1] }}>
                      <span style={{ fontWeight: t.font.weight.semibold, fontSize: t.font.size.lg, color: t.color.successText }}>{c.theme}</span>
                      <span style={{ fontSize: t.font.size.sm, color: t.color.textMuted }}>{c.count} mentions</span>
                    </div>
                    {c.examples.map((ex, j) => (
                      <p key={j} style={{ margin: '2px 0', fontSize: t.font.size.md, color: t.color.textSecondary }}>
                        — "{ex}"
                      </p>
                    ))}
                  </div>
                ))}
              </div>
            </>
          )}

          {(report.key_debates ?? []).length > 0 && (
            <>
              <h3 style={{ fontSize: t.font.size.xl, fontWeight: t.font.weight.semibold, marginBottom: t.space[3] }}>Key Debates</h3>
              <div style={{ display: 'flex', flexDirection: 'column', gap: t.space[3], marginBottom: t.space[6] }}>
                {report.key_debates!.map((debate, i) => (
                  <div key={i} style={{
                    padding: t.space[4], borderRadius: t.radius.md, border: `1px solid ${t.color.border}`, background: t.color.bgPage,
                    boxShadow: '0 1px 3px rgba(0,0,0,0.04)',
                  }}>
                    <div style={{ fontWeight: t.font.weight.semibold, fontSize: 15, marginBottom: t.space[3], color: t.color.textPrimary }}>
                      {debate.topic}
                    </div>
                    <div style={{ display: 'flex', gap: t.space[4], marginBottom: t.space[3] }}>
                      <div style={{ flex: 1 }}>
                        <div style={{
                          fontSize: t.font.size.sm, fontWeight: t.font.weight.semibold, color: t.color.successText,
                          marginBottom: t.space[1], textTransform: 'uppercase', letterSpacing: '0.5px',
                        }}>
                          For
                        </div>
                        <ul style={{ margin: 0, paddingLeft: t.space[4] }}>
                          {(debate.for_arguments ?? []).map((arg, j) => (
                            <li key={j} style={{ fontSize: t.font.size.md, color: t.color.textStrong, marginBottom: t.space[1], lineHeight: 1.5 }}>
                              {arg}
                            </li>
                          ))}
                        </ul>
                      </div>
                      <div style={{ width: 1, background: t.color.border, flexShrink: 0 }} />
                      <div style={{ flex: 1 }}>
                        <div style={{
                          fontSize: t.font.size.sm, fontWeight: t.font.weight.semibold, color: t.color.dangerText,
                          marginBottom: t.space[1], textTransform: 'uppercase', letterSpacing: '0.5px',
                        }}>
                          Against
                        </div>
                        <ul style={{ margin: 0, paddingLeft: t.space[4] }}>
                          {(debate.against_arguments ?? []).map((arg, j) => (
                            <li key={j} style={{ fontSize: t.font.size.md, color: t.color.textStrong, marginBottom: t.space[1], lineHeight: 1.5 }}>
                              {arg}
                            </li>
                          ))}
                        </ul>
                      </div>
                    </div>
                    <div style={{
                      paddingTop: 10, borderTop: `1px solid ${t.color.bgSubtle}`,
                      fontSize: t.font.size.md, color: t.color.textSecondary, fontStyle: 'italic',
                    }}>
                      {debate.resolution}
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}

          <h3 style={{ fontSize: t.font.size.xl, fontWeight: t.font.weight.semibold, marginBottom: t.space[3] }}>Criticism Patterns</h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: t.space[2], marginBottom: t.space[6] }}>
            {(report.criticism_clusters || []).map((c, i) => (
              <div key={i} style={{
                padding: t.space[3], borderRadius: t.radius.md, border: `1px solid ${t.color.dangerTint}`,
                background: t.color.dangerSubtle,
                boxShadow: '0 1px 3px rgba(239,68,68,0.06)',
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: t.space[1] }}>
                  <span style={{ fontWeight: t.font.weight.semibold, fontSize: t.font.size.lg }}>{c.theme}</span>
                  <span style={{ fontSize: t.font.size.sm, color: t.color.textMuted }}>{c.count} mentions</span>
                </div>
                {c.examples.map((ex, j) => (
                  <p key={j} style={{ margin: '2px 0', fontSize: t.font.size.md, color: t.color.textSecondary }}>
                    — "{ex}"
                  </p>
                ))}
              </div>
            ))}
          </div>

          <h3 style={{ fontSize: t.font.size.xl, fontWeight: t.font.weight.semibold, marginBottom: t.space[3] }}>Improvement Suggestions</h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: t.space[1], marginBottom: t.space[8] }}>
            {(report.improvements || []).map((imp, i) => (
              <div key={i} style={{
                display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                padding: '10px 14px', borderRadius: t.radius.md, border: `1px solid ${t.color.successTint}`,
                background: t.color.successLight,
                boxShadow: '0 1px 3px rgba(34,197,94,0.06)',
              }}>
                <span style={{ fontSize: t.font.size.lg, color: t.color.textPrimary }}>{imp.suggestion}</span>
                <span style={{ fontSize: t.font.size.sm, color: t.color.textMuted, whiteSpace: 'nowrap', marginLeft: t.space[2] }}>
                  ×{imp.frequency}
                </span>
              </div>
            ))}
          </div>

          {report.next_steps && report.next_steps.length > 0 && (
            <>
              <h3 style={{ fontSize: t.font.size.xl, fontWeight: t.font.weight.semibold, marginBottom: t.space[3] }}>Recommended Actions</h3>
              <div style={{ display: 'flex', flexDirection: 'column', gap: t.space[2], marginBottom: t.space[8] }}>
                {report.next_steps.map((step, i) => {
                  const priorityColor = step.priority === 'P0' ? t.color.danger
                    : step.priority === 'P1' ? t.color.warning
                    : t.color.info
                  return (
                    <div key={i} style={{
                      padding: t.space[3], borderRadius: t.radius.md,
                      border: `1px solid ${priorityColor}30`,
                      background: t.color.bgPage,
                      boxShadow: '0 1px 3px rgba(0,0,0,0.04)',
                    }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: t.space[2], marginBottom: t.space[1] }}>
                        <span style={{
                          display: 'inline-block',
                          padding: '2px 8px',
                          borderRadius: t.radius.sm,
                          fontSize: t.font.size.xs,
                          fontWeight: t.font.weight.bold,
                          color: t.color.textInverse,
                          background: priorityColor,
                        }}>
                          {step.priority}
                        </span>
                        <span style={{ fontSize: t.font.size.lg, fontWeight: t.font.weight.semibold, color: t.color.textPrimary }}>
                          {step.action}
                        </span>
                      </div>
                      <p style={{ margin: '0 0 8px', fontSize: t.font.size.md, color: t.color.textSecondary }}>
                        {step.rationale}
                      </p>
                      {(step.segment_impact?.length ?? 0) > 0 && (
                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: t.space[1] }}>
                          {step.segment_impact.map((seg, j) => (
                            <span key={j} style={{
                              fontSize: t.font.size.xs,
                              padding: '2px 6px',
                              borderRadius: t.radius.lg,
                              background: t.color.bgGray,
                              color: t.color.grayText,
                            }}>
                              {seg}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>
            </>
          )}
        </>
      )}
    </div>
  )
}
