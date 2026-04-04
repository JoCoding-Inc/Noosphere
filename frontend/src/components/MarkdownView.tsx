import { type ComponentProps, useMemo } from 'react'
import ReactMarkdown from 'react-markdown'
import { t } from '../tokens'

const MD_COMPONENTS: ComponentProps<typeof ReactMarkdown>['components'] = {
  h1: ({ children }) => (
    <h1 style={{ fontSize: 24, fontWeight: 800, letterSpacing: '-0.03em', margin: '0 0 16px' }}>{children}</h1>
  ),
  h2: ({ children }) => (
    <h2 style={{ fontSize: 19, fontWeight: t.font.weight.bold, letterSpacing: '-0.02em', margin: '32px 0 12px', paddingBottom: t.space[2], borderBottom: `1px solid ${t.color.border}` }}>{children}</h2>
  ),
  h3: ({ children }) => (
    <h3 style={{ fontSize: 15, fontWeight: t.font.weight.bold, margin: '24px 0 8px', color: t.color.textPrimary }}>{children}</h3>
  ),
  p: ({ children }) => (
    <p style={{ margin: '0 0 14px', color: t.color.textPrimary }}>{children}</p>
  ),
  ul: ({ children }) => (
    <ul style={{ margin: '0 0 14px', paddingLeft: 22 }}>{children}</ul>
  ),
  ol: ({ children }) => (
    <ol style={{ margin: '0 0 14px', paddingLeft: 22 }}>{children}</ol>
  ),
  li: ({ children }) => (
    <li style={{ margin: t.space[1] + ' 0', color: t.color.textPrimary }}>{children}</li>
  ),
  strong: ({ children }) => (
    <strong style={{ fontWeight: t.font.weight.bold, color: t.color.textPrimary }}>{children}</strong>
  ),
  em: ({ children }) => (
    <em style={{ fontStyle: 'italic', color: t.color.textSecondary }}>{children}</em>
  ),
  hr: () => (
    <hr style={{ border: 'none', borderTop: `1px solid ${t.color.border}`, margin: '24px 0' }} />
  ),
  blockquote: ({ children }) => (
    <blockquote style={{
      margin: '0 0 14px', padding: `10px ${t.space[4]}`,
      borderLeft: `3px solid ${t.color.accent}`, background: '#f8f5ff',
      borderRadius: '0 8px 8px 0', color: t.color.textStrong,
    }}>{children}</blockquote>
  ),
  code: ({ children }) => (
    <code style={{
      background: t.color.bgSubtle, padding: '2px 6px', borderRadius: t.radius.sm,
      fontSize: t.font.size.md, fontFamily: 'monospace', color: t.color.accentDark,
    }}>{children}</code>
  ),
}

export function MarkdownView({ content }: { content: string | null | undefined }) {
  // Normalize curly/smart quotes to ASCII so CommonMark bold delimiter rules work correctly
  // Then insert zero-width joiner (U+200D) between ** and adjacent quotes:
  // CommonMark spec says ** followed/preceded by a punctuation char (like ") is not a valid
  // flanking delimiter run unless surrounded by whitespace/punctuation on the other side.
  // U+200D is category Cf (not whitespace, not punctuation), so it makes ** flanking-valid.
  const normalized = useMemo(() => content
    ? content
        .replace(/[\u201C\u201D]/g, '"')
        .replace(/[\u2018\u2019]/g, "'")
        .replace(/\*\*(['"'"])/g, '**\u200D$1')
        .replace(/(['"'"])\*\*/g, '$1\u200D**')
    : content, [content])
  if (!normalized?.trim()) {
    return (
      <div style={{ padding: 48, textAlign: 'center', color: t.color.textMuted, fontSize: t.font.size.lg }}>
        <div style={{ fontSize: 28, marginBottom: t.space[3] }}>📄</div>
        No analysis available.
      </div>
    )
  }

  return (
    <div style={{ color: t.color.textPrimary, lineHeight: 1.75, fontSize: 15 }}>
      <ReactMarkdown components={MD_COMPONENTS}>
        {normalized}
      </ReactMarkdown>
    </div>
  )
}
