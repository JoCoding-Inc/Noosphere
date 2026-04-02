const COLLAPSE_THRESHOLD = 3

export interface ThreadCollapseProps {
  collapsibleThreads?: Map<string, number>
  expandedThreads?: Set<string>
  onToggleThread?: (parentId: string) => void
}

interface ButtonProps extends ThreadCollapseProps {
  postId: string
}

export function ThreadCollapseButton({ postId, collapsibleThreads, expandedThreads, onToggleThread }: ButtonProps) {
  if (!collapsibleThreads || !expandedThreads || !onToggleThread) return null
  const totalReplies = collapsibleThreads.get(postId)
  if (totalReplies == null || totalReplies <= COLLAPSE_THRESHOLD) return null

  const isExpanded = expandedThreads.has(postId)
  const hiddenCount = totalReplies - COLLAPSE_THRESHOLD

  return (
    <div style={{ marginTop: 6, marginBottom: 2, paddingLeft: 16 }}>
      <button
        onClick={() => onToggleThread(postId)}
        style={{
          display: 'inline-flex', alignItems: 'center', gap: 5,
          padding: '4px 10px', fontSize: 12, fontWeight: 500,
          borderRadius: 6, border: '1px solid #e2e8f0',
          background: '#f8fafc', color: '#6366f1',
          cursor: 'pointer', transition: 'all 0.15s',
        }}
      >
        {isExpanded
          ? `Hide ${hiddenCount} ${hiddenCount === 1 ? 'reply' : 'replies'}`
          : `Show ${hiddenCount} more ${hiddenCount === 1 ? 'reply' : 'replies'}`}
        <span style={{ fontSize: 10 }}>{isExpanded ? '\u25B2' : '\u25BC'}</span>
      </button>
    </div>
  )
}
