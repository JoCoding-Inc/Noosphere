import type { SocialPost } from '../../types'
import { getThreadedPosts } from './threadUtils'

interface Props { posts: SocialPost[] }

export function IndieHackersUI({ posts }: Props) {
  const { topLevel, getReplies } = getThreadedPosts(posts)

  function renderReplies(parentId: string, depth: number, baseDelay: number) {
    const replies = getReplies(parentId)
    if (replies.length === 0) return null
    return replies.map((reply, ri) => (
      <div key={reply.id} className="post-item" style={{
        borderTop: depth === 1 ? '1px solid #f0f0f0' : 'none',
        padding: `10px 16px 10px ${16 + depth * 16}px`,
        background: depth % 2 === 1 ? '#fafbfc' : '#f5f6f8',
        animationDelay: `${baseDelay + (ri + 1) * 80}ms`,
      }}>
        <div style={{ display: 'flex', gap: 8, alignItems: 'flex-start' }}>
          <div style={{
            width: Math.max(26 - depth * 2, 20), height: Math.max(26 - depth * 2, 20),
            borderRadius: '50%',
            background: `hsl(${(reply.author_name.charCodeAt(0) * 59) % 360}, 50%, 65%)`,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 11, fontWeight: 700, color: '#fff', flexShrink: 0,
          }}>
            {reply.author_name[0].toUpperCase()}
          </div>
          <div style={{ flex: 1 }}>
            <span style={{ fontWeight: 600, fontSize: 13, color: '#1f2d3d' }}>{reply.author_name}</span>
            <span style={{ fontSize: 11, color: '#8492a6', marginLeft: 6 }}>· just now</span>
            <p style={{ margin: '4px 0 0', fontSize: 13, color: '#3d4852', lineHeight: 1.6 }}>{reply.content}</p>
          </div>
        </div>
        {renderReplies(reply.id, depth + 1, baseDelay + (ri + 1) * 80)}
      </div>
    ))
  }

  return (
    <div style={{ fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif' }}>
      {/* IH 헤더 */}
      <div style={{
        background: '#fff', borderRadius: '8px 8px 0 0',
        borderBottom: '2px solid #e0e0e0', padding: '10px 16px',
        display: 'flex', alignItems: 'center', gap: 8,
      }}>
        <span style={{ fontSize: 20 }}>🤠</span>
        <span style={{ fontWeight: 800, fontSize: 15, color: '#1f2d3d' }}>Indie Hackers</span>
        <span style={{ color: '#8492a6', fontSize: 12, marginLeft: 4 }}>/ discussions</span>
      </div>

      <div style={{ background: '#fafafa', borderRadius: '0 0 8px 8px', padding: '8px' }}>
        {topLevel.length === 0 && (
          <div style={{ padding: '24px', textAlign: 'center', color: '#8492a6', fontSize: 14 }}>
            No discussions yet...
          </div>
        )}
        {topLevel.map((post, i) => {
          const replies = getReplies(post.id)

          return (
            <div key={post.id} className="post-item" style={{
              background: '#fff', border: '1px solid #e4e7eb', borderRadius: 8,
              marginBottom: 10, overflow: 'hidden',
              animationDelay: `${i * 60}ms`,
            }}>
              <div style={{ padding: '14px 16px' }}>
                {/* 작성자 */}
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
                  <div style={{
                    width: 36, height: 36, borderRadius: '50%',
                    background: `hsl(${(post.author_name.charCodeAt(0) * 41) % 360}, 55%, 60%)`,
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    fontSize: 14, fontWeight: 700, color: '#fff', flexShrink: 0,
                  }}>
                    {post.author_name[0].toUpperCase()}
                  </div>
                  <div>
                    <div style={{ fontWeight: 600, fontSize: 14, color: '#1f2d3d' }}>{post.author_name}</div>
                    <div style={{ fontSize: 11, color: '#8492a6' }}>Indie Hacker · just now</div>
                  </div>
                  {/* 업보트 */}
                  <div style={{
                    marginLeft: 'auto', display: 'flex', flexDirection: 'column', alignItems: 'center',
                    cursor: 'pointer', gap: 1,
                  }}>
                    <span style={{ fontSize: 16, color: '#0cce6b', lineHeight: 1 }}>▲</span>
                    <span style={{ fontSize: 12, fontWeight: 700, color: '#3d4852' }}>{post.upvotes}</span>
                  </div>
                </div>

                <p style={{ margin: 0, fontSize: 14, color: '#3d4852', lineHeight: 1.7 }}>{post.content}</p>

                <div style={{ marginTop: 10, display: 'flex', gap: 12, fontSize: 12, color: '#8492a6' }}>
                  <span style={{ cursor: 'pointer', color: '#0cce6b', fontWeight: 600 }}>▲ Upvote</span>
                  <span style={{ cursor: 'pointer' }}>💬 {replies.length} replies</span>
                  <span style={{ cursor: 'pointer' }}>Share</span>
                </div>
              </div>

              {/* 댓글 (재귀) */}
              {renderReplies(post.id, 1, i * 60)}
            </div>
          )
        })}
      </div>
    </div>
  )
}
