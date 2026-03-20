import type { SocialPost } from '../../types'

interface Props { posts: SocialPost[] }

const REACTIONS = ['👍', '❤️', '🙌', '💡', '🤔']

export function LinkedInUI({ posts }: Props) {
  const topLevel = posts.filter(p => !p.parent_id)
  const replies = posts.filter(p => p.parent_id)
  const getReplies = (id: string) => replies.filter(r => r.parent_id === id)

  return (
    <div style={{ fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif', background: '#f3f2ef', padding: '0', borderRadius: 8 }}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {topLevel.length === 0 && (
          <div style={{
            background: '#fff', borderRadius: 8, padding: '24px',
            textAlign: 'center', color: '#666', fontSize: 14,
          }}>
            No posts yet...
          </div>
        )}
        {topLevel.map((post, i) => (
          <div key={post.id} className="post-item" style={{
            background: '#fff', borderRadius: 8,
            border: '1px solid rgba(0,0,0,0.08)',
            boxShadow: '0 0 0 1px rgba(0,0,0,0.04)',
            overflow: 'hidden',
            animationDelay: `${i * 60}ms`,
          }}>
            {/* 작성자 헤더 */}
            <div style={{ padding: '12px 16px 0', display: 'flex', gap: 10, alignItems: 'flex-start' }}>
              <div style={{
                width: 48, height: 48, borderRadius: '50%', flexShrink: 0,
                background: `linear-gradient(135deg, hsl(${(post.author_name.charCodeAt(0) * 47) % 360}, 55%, 55%), hsl(${(post.author_name.charCodeAt(0) * 47 + 60) % 360}, 55%, 45%))`,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: 18, fontWeight: 700, color: '#fff',
              }}>
                {post.author_name[0].toUpperCase()}
              </div>
              <div style={{ flex: 1 }}>
                <div style={{ fontWeight: 600, fontSize: 14, color: 'rgba(0,0,0,0.9)' }}>{post.author_name}</div>
                <div style={{ fontSize: 12, color: 'rgba(0,0,0,0.6)', lineHeight: 1.4 }}>
                  {post.action_type === 'post' ? 'Senior Professional · Tech Industry' : 'Reacting to this post'}
                </div>
                <div style={{ fontSize: 11, color: 'rgba(0,0,0,0.4)', marginTop: 1 }}>just now · 🌐</div>
              </div>
              <span style={{ fontSize: 18, color: '#0a66c2', cursor: 'pointer' }}>···</span>
            </div>

            {/* 포스트 내용 */}
            <div style={{ padding: '10px 16px' }}>
              <p style={{ margin: 0, fontSize: 14, color: 'rgba(0,0,0,0.9)', lineHeight: 1.6, whiteSpace: 'pre-line' }}>
                {post.content}
              </p>
            </div>

            {/* 반응 수 */}
            <div style={{ padding: '4px 16px', display: 'flex', justifyContent: 'space-between', fontSize: 12, color: 'rgba(0,0,0,0.6)' }}>
              <span>
                {REACTIONS.slice(0, 3).join('')} {post.upvotes + 12}
              </span>
              <span>{getReplies(post.id).length} comments</span>
            </div>

            {/* 액션 버튼 */}
            <div style={{
              borderTop: '1px solid rgba(0,0,0,0.08)',
              padding: '4px 8px',
              display: 'flex', justifyContent: 'space-around',
            }}>
              {['👍 Like', '💬 Comment', '↗️ Repost', '✉️ Send'].map(action => (
                <button key={action} style={{
                  background: 'none', border: 'none', cursor: 'pointer',
                  padding: '8px 12px', fontSize: 13, color: 'rgba(0,0,0,0.6)',
                  fontWeight: 600, borderRadius: 4,
                  display: 'flex', alignItems: 'center', gap: 4,
                }}>
                  {action}
                </button>
              ))}
            </div>

            {/* 댓글 */}
            {getReplies(post.id).map((reply, ri) => (
              <div key={reply.id} className="post-item" style={{
                borderTop: '1px solid rgba(0,0,0,0.06)',
                padding: '10px 16px',
                display: 'flex', gap: 8,
                animationDelay: `${(i * 60) + (ri + 1) * 80}ms`,
              }}>
                <div style={{
                  width: 32, height: 32, borderRadius: '50%', flexShrink: 0,
                  background: `linear-gradient(135deg, hsl(${(reply.author_name.charCodeAt(0) * 53) % 360}, 50%, 60%), hsl(${(reply.author_name.charCodeAt(0) * 53 + 60) % 360}, 50%, 50%))`,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: 13, fontWeight: 700, color: '#fff',
                }}>
                  {reply.author_name[0].toUpperCase()}
                </div>
                <div style={{
                  background: '#f2f2f2', borderRadius: '0 8px 8px 8px',
                  padding: '8px 12px', flex: 1,
                }}>
                  <div style={{ fontWeight: 600, fontSize: 13, color: 'rgba(0,0,0,0.9)', marginBottom: 3 }}>{reply.author_name}</div>
                  <p style={{ margin: 0, fontSize: 13, color: 'rgba(0,0,0,0.8)', lineHeight: 1.5 }}>{reply.content}</p>
                </div>
              </div>
            ))}
          </div>
        ))}
      </div>
    </div>
  )
}
