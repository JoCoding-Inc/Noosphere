import ReactMarkdown from 'react-markdown'

export function MarkdownView({ content }: { content: string }) {
  return (
    <div style={{ color: '#1e293b', lineHeight: 1.75, fontSize: 15 }}>
      <ReactMarkdown
        components={{
          h1: ({ children }) => (
            <h1 style={{ fontSize: 24, fontWeight: 800, letterSpacing: '-0.03em', margin: '0 0 16px' }}>{children}</h1>
          ),
          h2: ({ children }) => (
            <h2 style={{ fontSize: 19, fontWeight: 700, letterSpacing: '-0.02em', margin: '32px 0 12px', paddingBottom: 8, borderBottom: '1px solid #e2e8f0' }}>{children}</h2>
          ),
          h3: ({ children }) => (
            <h3 style={{ fontSize: 15, fontWeight: 700, margin: '24px 0 8px', color: '#374151' }}>{children}</h3>
          ),
          p: ({ children }) => (
            <p style={{ margin: '0 0 14px', color: '#374151' }}>{children}</p>
          ),
          ul: ({ children }) => (
            <ul style={{ margin: '0 0 14px', paddingLeft: 22 }}>{children}</ul>
          ),
          ol: ({ children }) => (
            <ol style={{ margin: '0 0 14px', paddingLeft: 22 }}>{children}</ol>
          ),
          li: ({ children }) => (
            <li style={{ margin: '4px 0', color: '#374151' }}>{children}</li>
          ),
          strong: ({ children }) => (
            <strong style={{ fontWeight: 700, color: '#1e293b' }}>{children}</strong>
          ),
          em: ({ children }) => (
            <em style={{ fontStyle: 'italic', color: '#475569' }}>{children}</em>
          ),
          hr: () => (
            <hr style={{ border: 'none', borderTop: '1px solid #e2e8f0', margin: '24px 0' }} />
          ),
          blockquote: ({ children }) => (
            <blockquote style={{
              margin: '0 0 14px', padding: '10px 16px',
              borderLeft: '3px solid #8b5cf6', background: '#f8f5ff',
              borderRadius: '0 8px 8px 0', color: '#475569',
            }}>{children}</blockquote>
          ),
          code: ({ children }) => (
            <code style={{
              background: '#f1f5f9', padding: '2px 6px', borderRadius: 4,
              fontSize: 13, fontFamily: 'monospace', color: '#7c3aed',
            }}>{children}</code>
          ),
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  )
}
