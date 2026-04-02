import type { ReportJSON } from '../types'
import { VERDICT_CONFIG, PLATFORM_COLORS } from '../constants'

const SENTIMENT_DOT: Record<string, string> = {
  positive: '#22c55e',
  neutral:  '#94a3b8',
  negative: '#ef4444',
}

export function ReportView({ report }: { report: ReportJSON | null | undefined }) {
  if (!report || !report.verdict) {
    return (
      <div style={{ padding: 48, textAlign: 'center', color: '#94a3b8', fontSize: 14 }}>
        <div style={{ marginBottom: 12, display: 'flex', justifyContent: 'center' }}>
          <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
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
  const adoptionColor = adoptionScore == null ? '#94a3b8'
    : adoptionScore <= 30 ? '#ef4444'
    : adoptionScore <= 60 ? '#f59e0b'
    : adoptionScore <= 80 ? '#84cc16'
    : '#22c55e'

  return (
    <div>
      <div style={{ display: 'flex', gap: 16, marginBottom: 24, flexWrap: 'wrap' }}>
        <div style={{
          flex: 1, minWidth: 200,
          padding: 20, borderRadius: 10,
          border: `1px solid ${v.color}20`,
          background: `${v.color}08`,
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 4 }}>
            <svg
              width="24" height="24" viewBox="0 0 24 24"
              fill="none" stroke={v.color} strokeWidth="2"
              aria-hidden="true"
              style={{ flexShrink: 0 }}
              dangerouslySetInnerHTML={{ __html: v.icon }}
            />
            <span style={{ fontSize: 20, fontWeight: 700, color: v.color }}>{v.label}</span>
          </div>
          <p style={{ margin: 0, fontSize: 14, color: '#64748b' }}>
            Based on {report.evidence_count} simulated interactions
          </p>
        </div>

        {adoptionScore != null && (
          <div style={{
            display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
            padding: 20, borderRadius: 10, minWidth: 140,
            border: `1px solid ${adoptionColor}20`,
            background: `${adoptionColor}08`,
          }}>
            <div style={{ position: 'relative', width: 72, height: 72, marginBottom: 8 }}>
              <svg width="72" height="72" viewBox="0 0 72 72" style={{ transform: 'rotate(-90deg)' }}>
                <circle cx="36" cy="36" r="30" fill="none" stroke="#e2e8f0" strokeWidth="6" />
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
                fontSize: 20, fontWeight: 700, color: adoptionColor,
              }}>
                {adoptionScore}
              </span>
            </div>
            <span style={{ fontSize: 12, fontWeight: 600, color: '#64748b' }}>Adoption Score</span>
            <span style={{ fontSize: 11, color: '#94a3b8' }}>{adoptionScore} / 100</span>
          </div>
        )}

        {report.consensus_score !== undefined && (
          <div style={{
            display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
            padding: 20, borderRadius: 10, minWidth: 120,
            border: '1px solid #10b98120',
            background: '#10b98108',
          }}>
            <div style={{ fontSize: 11, color: '#94a3b8', marginBottom: 4 }}>Platform Consensus</div>
            <div style={{ fontSize: 22, fontWeight: 700, color: '#10b981' }}>
              {report.consensus_score}%
            </div>
          </div>
        )}

        {report.response_rate !== undefined && (
          <div style={{
            display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
            padding: 20, borderRadius: 10, minWidth: 120,
            border: '1px solid #3b82f620',
            background: '#3b82f608',
          }}>
            <div style={{ fontSize: 11, color: '#94a3b8', marginBottom: 4 }}>Response Rate</div>
            <div style={{ fontSize: 22, fontWeight: 700, color: '#3b82f6' }}>
              {Math.round(report.response_rate * 100)}%
            </div>
          </div>
        )}
      </div>

      {hasValidation && (
        <div
          style={{
            display: 'inline-flex', alignItems: 'center', gap: 6,
            background: '#fffbeb', color: '#92400e',
            border: '1px solid #fde68a', borderRadius: 20,
            fontSize: 12, fontWeight: 600, padding: '5px 12px',
            marginBottom: 16, cursor: 'default',
          }}
          title={report.validation?.details?.join('\n') ?? ''}
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#f59e0b" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ flexShrink: 0 }} aria-hidden="true">
            <path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/>
            <line x1="12" y1="9" x2="12" y2="13"/>
            <line x1="12" y1="17" x2="12.01" y2="17"/>
          </svg>
          {report.validation?.corrections_applied} auto-corrections applied
        </div>
      )}

      {report.platform_divergence && report.platform_divergence.length > 0 && (
        <div style={{ background: '#1e1b4b22', border: '1px solid #6366f1', borderRadius: 8, padding: 12, marginBottom: 12 }}>
          <div style={{ fontWeight: 600, color: '#a5b4fc', fontSize: 13, marginBottom: 6 }}>
            Platform Divergence Detected
          </div>
          {report.platform_divergence.map((d, i) => (
            <div key={i} style={{ color: '#94a3b8', fontSize: 12 }}>
              {d.platform_a} vs {d.platform_b}: {d.gap_pct}%p gap — {d.direction}
            </div>
          ))}
        </div>
      )}

      {report.engagement_alerts && report.engagement_alerts.length > 0 && (
        <div style={{
          background: '#451a0322',
          border: '1px solid #f59e0b',
          borderRadius: 8,
          padding: 12,
          marginBottom: 24,
        }}>
          <div style={{ fontWeight: 600, color: '#f59e0b', fontSize: 13, marginBottom: 6 }}>
            Engagement Drop Detected
          </div>
          {report.engagement_alerts.map((alert, i) => (
            <div key={i} style={{ color: '#94a3b8', fontSize: 12 }}>
              Round {alert.round}: engagement dropped {alert.drop_pct}%
              ({alert.prev_engagement} → {alert.curr_engagement})
            </div>
          ))}
        </div>
      )}

      {report.attitude_shifts && report.attitude_shifts.length > 0 && (
        <div style={{ marginBottom: 24 }}>
          <div style={{ fontSize: 13, fontWeight: 600, color: '#e2e8f0', marginBottom: 12 }}>
            Notable Attitude Shifts
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {report.attitude_shifts.slice(0, 5).map((shift, i) => (
              <div key={i} style={{ background: '#1e293b', borderRadius: 6, padding: '8px 12px' }}>
                <span style={{ fontWeight: 600, color: '#e2e8f0', fontSize: 12 }}>
                  {shift.name}
                </span>
                <span style={{
                  marginLeft: 8, fontSize: 11,
                  color: shift.total_delta > 0 ? '#10b981' : '#ef4444'
                }}>
                  {(shift.total_delta ?? 0) > 0 ? '+' : ''}{(shift.total_delta ?? 0).toFixed(2)}
                </span>
                {shift.history[0]?.trigger_summary && (
                  <div style={{ color: '#64748b', fontSize: 11, marginTop: 4, fontStyle: 'italic' }}>
                    "{shift.history[0].trigger_summary}"
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {report.segment_attitude_shifts && report.segment_attitude_shifts.length > 0 && (
        <div style={{ marginBottom: 24 }}>
          <div style={{ fontSize: 13, fontWeight: 600, color: '#e2e8f0', marginBottom: 12 }}>
            Segment Attitude Shifts
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {report.segment_attitude_shifts.map((seg, i) => {
              const isLow = seg.confidence === 'low'
              return (
                <div key={i} style={{
                  background: '#1e293b', borderRadius: 6, padding: '8px 12px',
                  opacity: isLow ? 0.55 : 1,
                  border: isLow ? '1px dashed #64748b' : '1px solid transparent',
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <span style={{ fontWeight: 600, color: '#e2e8f0', fontSize: 12 }}>
                      {seg.segment}
                    </span>
                    <span style={{
                      fontSize: 11,
                      color: (seg.avg_delta ?? 0) > 0 ? '#10b981' : (seg.avg_delta ?? 0) < 0 ? '#ef4444' : '#94a3b8',
                    }}>
                      {(seg.avg_delta ?? 0) > 0 ? '+' : ''}{(seg.avg_delta ?? 0).toFixed(2)}
                    </span>
                    <span style={{ fontSize: 10, color: '#64748b' }}>
                      ({seg.shifted_count}/{seg.count} shifted)
                    </span>
                    {isLow && (
                      <span style={{ fontSize: 10, color: '#f59e0b', fontStyle: 'italic' }}>
                        (n&lt;5, reference only)
                      </span>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {report.qa_pairs && report.qa_pairs.length > 0 && (
        <div style={{ marginBottom: 24 }}>
          <div style={{ fontSize: 13, fontWeight: 600, color: '#e2e8f0', marginBottom: 12 }}>
            Community Q&A
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {report.qa_pairs.slice(0, 5).map((qa, i) => (
              <div key={i} style={{ background: '#1e293b', borderRadius: 6, padding: '10px 14px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6 }}>
                  <span style={{ fontSize: 10, background: '#334155', color: '#94a3b8', borderRadius: 4, padding: '2px 6px' }}>
                    {qa.platform}
                  </span>
                  <span style={{ fontSize: 11, color: '#64748b' }}>{qa.author_name}</span>
                </div>
                <div style={{ fontSize: 12, color: '#cbd5e1', marginBottom: qa.answers.length > 0 ? 8 : 0 }}>
                  Q: {qa.question_text}
                </div>
                {qa.answers.slice(0, 1).map((ans, j) => (
                  <div key={j} style={{ fontSize: 11, color: '#94a3b8', borderLeft: '2px solid #334155', paddingLeft: 8 }}>
                    A: {ans.text} <span style={{ color: '#64748b' }}>— {ans.author_name} {'👍'}{ans.upvotes}</span>
                  </div>
                ))}
                {!qa.answered && (
                  <div style={{ fontSize: 11, color: '#64748b', fontStyle: 'italic' }}>No answers yet</div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      <h3 style={{ fontSize: 16, fontWeight: 600, marginBottom: 12 }}>Segment Reactions</h3>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12, marginBottom: 24 }}>
        {(report.segments || []).map(seg => (
          <div key={seg.name} style={{
            padding: 14, borderRadius: 8, border: '1px solid #e2e8f0', background: '#fff',
            boxShadow: 'var(--shadow-card)',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
              <span style={{
                  width: 8, height: 8, borderRadius: '50%',
                  background: SENTIMENT_DOT[seg.sentiment] || '#94a3b8',
                  display: 'inline-block', flexShrink: 0,
                }} />
              <span style={{ fontWeight: 600, fontSize: 14 }}>
                {seg.name.replace('_', ' ').replace(/\b\w/g, c => c.toUpperCase())}
              </span>
            </div>
            <p style={{ margin: '0 0 8px', fontSize: 14, color: '#475569' }}>{seg.summary}</p>
            {(seg.key_quotes || []).map((q, i) => (
              <p key={i} style={{
                margin: '4px 0', paddingLeft: 12, borderLeft: '3px solid #e2e8f0',
                fontSize: 13, color: '#64748b', fontStyle: 'italic',
              }}>"{q}"</p>
            ))}
          </div>
        ))}
      </div>

      {(report.praise_clusters ?? []).length > 0 && (
        <>
          <h3 style={{ fontSize: 16, fontWeight: 600, marginBottom: 12 }}>What Resonated</h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 24 }}>
            {report.praise_clusters!.map((c, i) => (
              <div key={i} style={{
                padding: 12, borderRadius: 8, border: '1px solid #bbf7d0',
                background: '#f0fdf4',
                boxShadow: '0 1px 3px rgba(34,197,94,0.06)',
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                  <span style={{ fontWeight: 600, fontSize: 14, color: '#16a34a' }}>{c.theme}</span>
                  <span style={{ fontSize: 12, color: '#94a3b8' }}>{c.count} mentions</span>
                </div>
                {c.examples.map((ex, j) => (
                  <p key={j} style={{ margin: '2px 0', fontSize: 13, color: '#64748b' }}>
                    — "{ex}"
                  </p>
                ))}
              </div>
            ))}
          </div>
        </>
      )}

      {report.platform_segments && Object.keys(report.platform_segments).length > 0 && (
        <>
          <h3 style={{ fontSize: 16, fontWeight: 600, marginBottom: 12 }}>Platform Breakdown</h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12, marginBottom: 24 }}>
            {Object.entries(report.platform_segments).map(([platform, segments]) => (
              <div key={platform} style={{
                padding: 14, borderRadius: 8, border: '1px solid #e2e8f0', background: '#fff',
                boxShadow: 'var(--shadow-card)',
              }}>
                <div style={{ fontWeight: 600, fontSize: 14, marginBottom: 10, color: '#1e293b' }}>
                  {platform.replace('_', ' ').replace(/\b\w/g, c => c.toUpperCase())}
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                  {Object.entries(segments).map(([segName, counts]) => {
                    const posPercent = counts.total > 0 ? Math.round((counts.positive / counts.total) * 100) : 0
                    const neuPercent = counts.total > 0 ? Math.round((counts.neutral / counts.total) * 100) : 0
                    const negPercent = counts.total > 0 ? Math.round((counts.negative / counts.total) * 100) : 0
                    return (
                      <div key={segName}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
                          <span style={{ fontSize: 13, color: '#475569' }}>
                            {segName.replace('_', ' ').replace(/\b\w/g, c => c.toUpperCase())}
                          </span>
                          <span style={{ fontSize: 12, color: '#94a3b8' }}>{counts.total} responses</span>
                        </div>
                        <div style={{ display: 'flex', height: 6, borderRadius: 3, overflow: 'hidden', background: '#f1f5f9' }}>
                          {posPercent > 0 && (
                            <div style={{ width: `${posPercent}%`, background: '#22c55e' }} title={`Positive ${posPercent}%`} />
                          )}
                          {neuPercent > 0 && (
                            <div style={{ width: `${neuPercent}%`, background: '#94a3b8' }} title={`Neutral ${neuPercent}%`} />
                          )}
                          {negPercent > 0 && (
                            <div style={{ width: `${negPercent}%`, background: '#ef4444' }} title={`Negative ${negPercent}%`} />
                          )}
                        </div>
                        <div style={{ display: 'flex', gap: 12, marginTop: 3 }}>
                          <span style={{ fontSize: 11, color: '#22c55e' }}>{posPercent}% pos</span>
                          <span style={{ fontSize: 11, color: '#94a3b8' }}>{neuPercent}% neu</span>
                          <span style={{ fontSize: 11, color: '#ef4444' }}>{negPercent}% neg</span>
                        </div>
                      </div>
                    )
                  })}
                </div>
              </div>
            ))}
          </div>
        </>
      )}

      {report.region_sentiment && Object.keys(report.region_sentiment).length > 0 && (
        <>
          <h3 style={{ fontSize: 16, fontWeight: 600, marginBottom: 12 }}>Regional Sentiment</h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12, marginBottom: 24 }}>
            {Object.entries(report.region_sentiment).map(([region, counts]) => {
              const posPercent = counts.total > 0 ? Math.round((counts.positive / counts.total) * 100) : 0
              const neuPercent = counts.total > 0 ? Math.round((counts.neutral / counts.total) * 100) : 0
              const negPercent = counts.total > 0 ? Math.round((counts.negative / counts.total) * 100) : 0
              return (
                <div key={region} style={{
                  padding: 14, borderRadius: 8, border: '1px solid #e2e8f0', background: '#fff',
                  boxShadow: 'var(--shadow-card)',
                }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                    <span style={{ fontWeight: 600, fontSize: 14, color: '#1e293b' }}>
                      {region}
                    </span>
                    <span style={{ fontSize: 12, color: '#94a3b8' }}>{counts.total} responses</span>
                  </div>
                  <div style={{ display: 'flex', height: 6, borderRadius: 3, overflow: 'hidden', background: '#f1f5f9' }}>
                    {posPercent > 0 && (
                      <div style={{ width: `${posPercent}%`, background: '#22c55e' }} title={`Positive ${posPercent}%`} />
                    )}
                    {neuPercent > 0 && (
                      <div style={{ width: `${neuPercent}%`, background: '#94a3b8' }} title={`Neutral ${neuPercent}%`} />
                    )}
                    {negPercent > 0 && (
                      <div style={{ width: `${negPercent}%`, background: '#ef4444' }} title={`Negative ${negPercent}%`} />
                    )}
                  </div>
                  <div style={{ display: 'flex', gap: 12, marginTop: 3 }}>
                    <span style={{ fontSize: 11, color: '#22c55e' }}>{counts.positive_pct ?? posPercent}% pos</span>
                    <span style={{ fontSize: 11, color: '#94a3b8' }}>{neuPercent}% neu</span>
                    <span style={{ fontSize: 11, color: '#ef4444' }}>{counts.negative_pct ?? negPercent}% neg</span>
                  </div>
                </div>
              )
            })}
          </div>
        </>
      )}

      {(report.key_debates ?? []).length > 0 && (
        <>
          <h3 style={{ fontSize: 16, fontWeight: 600, marginBottom: 12 }}>Key Debates</h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12, marginBottom: 24 }}>
            {report.key_debates!.map((debate, i) => (
              <div key={i} style={{
                padding: 16, borderRadius: 8, border: '1px solid #e2e8f0', background: '#fff',
                boxShadow: '0 1px 3px rgba(0,0,0,0.04)',
              }}>
                <div style={{ fontWeight: 600, fontSize: 15, marginBottom: 12, color: '#1e293b' }}>
                  {debate.topic}
                </div>
                <div style={{ display: 'flex', gap: 16, marginBottom: 12 }}>
                  <div style={{ flex: 1 }}>
                    <div style={{
                      fontSize: 12, fontWeight: 600, color: '#16a34a',
                      marginBottom: 6, textTransform: 'uppercase', letterSpacing: '0.5px',
                    }}>
                      For
                    </div>
                    <ul style={{ margin: 0, paddingLeft: 16 }}>
                      {(debate.for_arguments ?? []).map((arg, j) => (
                        <li key={j} style={{ fontSize: 13, color: '#475569', marginBottom: 4, lineHeight: 1.5 }}>
                          {arg}
                        </li>
                      ))}
                    </ul>
                  </div>
                  <div style={{ width: 1, background: '#e2e8f0', flexShrink: 0 }} />
                  <div style={{ flex: 1 }}>
                    <div style={{
                      fontSize: 12, fontWeight: 600, color: '#dc2626',
                      marginBottom: 6, textTransform: 'uppercase', letterSpacing: '0.5px',
                    }}>
                      Against
                    </div>
                    <ul style={{ margin: 0, paddingLeft: 16 }}>
                      {(debate.against_arguments ?? []).map((arg, j) => (
                        <li key={j} style={{ fontSize: 13, color: '#475569', marginBottom: 4, lineHeight: 1.5 }}>
                          {arg}
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>
                <div style={{
                  paddingTop: 10, borderTop: '1px solid #f1f5f9',
                  fontSize: 13, color: '#64748b', fontStyle: 'italic',
                }}>
                  {debate.resolution}
                </div>
              </div>
            ))}
          </div>
        </>
      )}

      <h3 style={{ fontSize: 16, fontWeight: 600, marginBottom: 12 }}>Criticism Patterns</h3>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 24 }}>
        {(report.criticism_clusters || []).map((c, i) => (
          <div key={i} style={{
            padding: 12, borderRadius: 8, border: '1px solid #fecdd3',
            background: '#fff1f2',
            boxShadow: '0 1px 3px rgba(239,68,68,0.06)',
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
              <span style={{ fontWeight: 600, fontSize: 14 }}>{c.theme}</span>
              <span style={{ fontSize: 12, color: '#94a3b8' }}>{c.count} mentions</span>
            </div>
            {c.examples.map((ex, j) => (
              <p key={j} style={{ margin: '2px 0', fontSize: 13, color: '#64748b' }}>
                — "{ex}"
              </p>
            ))}
          </div>
        ))}
      </div>

      <h3 style={{ fontSize: 16, fontWeight: 600, marginBottom: 12 }}>Improvement Suggestions</h3>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginBottom: 32 }}>
        {(report.improvements || []).map((imp, i) => (
          <div key={i} style={{
            display: 'flex', justifyContent: 'space-between', alignItems: 'center',
            padding: '10px 14px', borderRadius: 8, border: '1px solid #d1fae5',
            background: '#f0fdf4',
            boxShadow: '0 1px 3px rgba(34,197,94,0.06)',
          }}>
            <span style={{ fontSize: 14, color: '#1e293b' }}>{imp.suggestion}</span>
            <span style={{ fontSize: 12, color: '#94a3b8', whiteSpace: 'nowrap', marginLeft: 8 }}>
              ×{imp.frequency}
            </span>
          </div>
        ))}
      </div>

      {report.next_steps && report.next_steps.length > 0 && (
        <>
          <h3 style={{ fontSize: 16, fontWeight: 600, marginBottom: 12 }}>Recommended Actions</h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginBottom: 32 }}>
            {report.next_steps.map((step, i) => {
              const priorityColor = step.priority === 'P0' ? '#ef4444'
                : step.priority === 'P1' ? '#f59e0b'
                : '#3b82f6'
              return (
                <div key={i} style={{
                  padding: 14, borderRadius: 8,
                  border: `1px solid ${priorityColor}30`,
                  background: '#fff',
                  boxShadow: '0 1px 3px rgba(0,0,0,0.04)',
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 6 }}>
                    <span style={{
                      display: 'inline-block',
                      padding: '2px 8px',
                      borderRadius: 4,
                      fontSize: 11,
                      fontWeight: 700,
                      color: '#fff',
                      background: priorityColor,
                    }}>
                      {step.priority}
                    </span>
                    <span style={{ fontSize: 14, fontWeight: 600, color: '#1e293b' }}>
                      {step.action}
                    </span>
                  </div>
                  <p style={{ margin: '0 0 8px', fontSize: 13, color: '#64748b' }}>
                    {step.rationale}
                  </p>
                  {(step.segment_impact?.length ?? 0) > 0 && (
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                      {step.segment_impact.map((seg, j) => (
                        <span key={j} style={{
                          fontSize: 11,
                          padding: '2px 6px',
                          borderRadius: 10,
                          background: '#e5e7eb',
                          color: '#374151',
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

      {report.archetype_narratives && report.archetype_narratives.length > 0 && (
        <>
          <h3 style={{ fontSize: 16, fontWeight: 600, marginBottom: 12 }}>Archetype Journey</h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 32 }}>
            {report.archetype_narratives.map((arc, i) => {
              const deltaColor = arc.attitude_delta > 0 ? '#22c55e' : arc.attitude_delta < 0 ? '#ef4444' : '#94a3b8'
              const journeyParts = arc.journey_summary.split(/\s*→\s*/)
              return (
                <div key={i} style={{
                  border: '1px solid #e2e8f0',
                  borderRadius: 8,
                  padding: '12px 16px',
                  background: '#fff',
                  boxShadow: '0 1px 3px rgba(0,0,0,0.04)',
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10, flexWrap: 'wrap' }}>
                    <span style={{ fontSize: 14, fontWeight: 600, color: '#1e293b' }}>
                      {arc.segment.replace(/\b\w/g, c => c.toUpperCase())}
                    </span>
                    <span style={{
                      fontSize: 11, padding: '2px 8px', borderRadius: 10,
                      background: '#e5e7eb', color: '#374151', fontWeight: 600,
                    }}>
                      {arc.persona_count} personas
                    </span>
                    <span style={{
                      fontSize: 12, fontWeight: 700, color: deltaColor,
                    }}>
                      {(arc.attitude_delta ?? 0) > 0 ? '+' : ''}{(arc.attitude_delta ?? 0).toFixed(2)}
                    </span>
                  </div>

                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: (arc.pivot_rounds?.length ?? 0) > 0 ? 10 : 0 }}>
                    {journeyParts.map((part, j) => {
                      const lower = part.trim().toLowerCase()
                      let bg = '#f1f5f9'
                      let fg = '#475569'
                      if (lower.includes('positive')) { bg = '#dcfce7'; fg = '#15803d' }
                      else if (lower.includes('mixed') || lower.includes('stable')) { bg = '#fef3c7'; fg = '#b45309' }
                      else if (lower.includes('skeptical')) { bg = '#ffedd5'; fg = '#c2410c' }
                      return (
                        <span key={j} style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                          <span style={{
                            fontSize: 12, padding: '3px 10px', borderRadius: 12,
                            background: bg, color: fg, fontWeight: 500,
                          }}>
                            {part.trim()}
                          </span>
                          {j < journeyParts.length - 1 && (
                            <span style={{ color: '#94a3b8', fontSize: 13 }}>→</span>
                          )}
                        </span>
                      )
                    })}
                  </div>

                  {(arc.pivot_rounds?.length ?? 0) > 0 && (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                      {(arc.pivot_rounds ?? []).map((pv, k) => {
                        const isNeg = pv.direction === 'negative' || (pv.delta_pct ?? 0) < 0
                        const arrow = isNeg ? '▼' : '▲'
                        const pvColor = isNeg ? '#ef4444' : '#22c55e'
                        const snippet = pv.trigger_post_snippet
                          ? (pv.trigger_post_snippet.length > 30
                              ? pv.trigger_post_snippet.slice(0, 30) + '...'
                              : pv.trigger_post_snippet)
                          : ''
                        return (
                          <div key={k} style={{ fontSize: 12, color: '#64748b', lineHeight: 1.6 }}>
                            <span style={{ color: pvColor, fontWeight: 600 }}>
                              {arrow} R{pv.round}
                            </span>
                            {' '}
                            <span style={{ color: pvColor }}>
                              {(pv.delta_pct ?? 0) > 0 ? '+' : ''}{pv.delta_pct ?? 0}%
                            </span>
                            {' '}
                            <span style={{ color: '#94a3b8' }}>by {pv.trigger_author}</span>
                            {' '}
                            <span style={{ fontStyle: 'italic' }}>"{snippet}"</span>
                          </div>
                        )
                      })}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </>
      )}

      {report.unaddressed_concerns && report.unaddressed_concerns.length > 0 && (
        <>
          <h3 style={{ fontSize: 16, fontWeight: 600, marginBottom: 12 }}>Unaddressed Concerns</h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 32 }}>
            {report.unaddressed_concerns.map((concern, i) => {
              const platColor = PLATFORM_COLORS[concern.platform as keyof typeof PLATFORM_COLORS] || '#94a3b8'
              const sentColor = concern.sentiment === 'negative' ? '#ef4444'
                : concern.sentiment === 'positive' ? '#22c55e'
                : '#94a3b8'
              return (
                <div key={i} style={{
                  padding: '10px 14px', borderRadius: 8,
                  border: '1px solid #fecdd3', background: '#fff',
                  boxShadow: '0 1px 3px rgba(0,0,0,0.04)',
                  borderLeft: `3px solid ${platColor}`,
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6, flexWrap: 'wrap' }}>
                    <span style={{
                      fontSize: 10, fontWeight: 700, padding: '1px 6px', borderRadius: 8,
                      background: `${platColor}18`, color: platColor,
                      textTransform: 'uppercase', letterSpacing: '0.04em',
                    }}>
                      {concern.platform}
                    </span>
                    <span style={{ fontSize: 12, fontWeight: 600, color: '#1e293b' }}>
                      {concern.author_name}
                    </span>
                    <span style={{
                      fontSize: 11, padding: '2px 6px', borderRadius: 10,
                      background: '#e5e7eb', color: '#374151',
                    }}>
                      {concern.author_segment}
                    </span>
                    <span style={{
                      fontSize: 10, width: 6, height: 6, borderRadius: '50%',
                      background: sentColor, display: 'inline-block', flexShrink: 0,
                    }} />
                    {concern.weighted_score != null && (
                      <span style={{ fontSize: 11, color: '#94a3b8', marginLeft: 'auto' }}>
                        score: {concern.weighted_score.toFixed(1)}
                      </span>
                    )}
                  </div>
                  <p style={{ margin: 0, fontSize: 13, color: '#475569', lineHeight: 1.5 }}>
                    "{concern.content_snippet}"
                  </p>
                </div>
              )
            })}
          </div>
        </>
      )}

    </div>
  )
}
