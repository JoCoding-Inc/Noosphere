import type { SocialPost } from '../../types'
import { getThreadedPosts } from './threadUtils'

interface Props { posts: SocialPost[] }

export function RedditUI({ posts }: Props) {
  const { topLevel, getReplies } = getThreadedPosts(posts)

  return (
    <div style={{ fontFamily: '-apple-system, BlinkMacSystemFont, "IBM Plex Sans", sans-serif' }}>
      {/* Reddit 헤더 */}
      <div style={{
        background: '#fff', border: '1px solid #edeff1', borderRadius: '4px 4px 0 0',
        padding: '8px 12px', display: 'flex', alignItems: 'center', gap: 8,
        borderBottom: 'none',
      }}>
        <span style={{ fontSize: 18 }}>🤖</span>
        <div>
          <span style={{ fontWeight: 700, fontSize: 14, color: '#1c1c1c' }}>r/startups</span>
          <span style={{ color: '#878a8c', fontSize: 12, marginLeft: 8 }}>
            {posts.length} posts · Simulation in progress
          </span>
        </div>
      </div>

      <div style={{ background: '#dae0e6', padding: '2px', borderRadius: '0 0 4px 4px' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          {topLevel.length === 0 && (
            <div style={{
              background: '#fff', padding: '24px', textAlign: 'center',
              color: '#878a8c', fontSize: 14, borderRadius: 4,
            }}>
              No posts yet...
            </div>
          )}
          {topLevel.map((post, i) => {
            const replies = getReplies(post.id)

            return (
              <div key={post.id} className="post-item" style={{
                background: '#fff', borderRadius: 4, overflow: 'hidden',
                animationDelay: `${i * 60}ms`,
              }}>
                {/* 메인 포스트 */}
                <div style={{ display: 'flex', gap: 0 }}>
                  {/* 투표 사이드바 */}
                  <div style={{
                    background: '#f8f9fa', width: 36, flexShrink: 0,
                    display: 'flex', flexDirection: 'column', alignItems: 'center',
                    padding: '8px 0', gap: 2,
                  }}>
                    <button style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#878a8c', fontSize: 16, padding: '2px', lineHeight: 1 }}>▲</button>
                    <span style={{ fontSize: 12, fontWeight: 700, color: '#1c1c1c' }}>{post.upvotes}</span>
                    <button style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#878a8c', fontSize: 16, padding: '2px', lineHeight: 1 }}>▼</button>
                  </div>

                  {/* 포스트 내용 */}
                  <div style={{ padding: '8px 8px 8px 8px', flex: 1 }}>
                    <div style={{ fontSize: 11, color: '#878a8c', marginBottom: 4 }}>
                      Posted by{' '}
                      <span style={{ color: '#0079d3', cursor: 'pointer' }}>u/{post.author_name.toLowerCase().replace(/\s/g, '_')}</span>
                    </div>
                    <p style={{ margin: '0 0 8px', fontSize: 14, color: '#1c1c1c', lineHeight: 1.5, fontWeight: 400 }}>
                      {post.content}
                    </p>
                    <div style={{ display: 'flex', gap: 12, fontSize: 12, color: '#878a8c' }}>
                      <button style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#878a8c', fontSize: 12, padding: 0, display: 'flex', alignItems: 'center', gap: 4 }}>
                        💬 {replies.length} Comments
                      </button>
                      <button style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#878a8c', fontSize: 12, padding: 0 }}>
                        Share
                      </button>
                      <button style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#878a8c', fontSize: 12, padding: 0 }}>
                        Save
                      </button>
                    </div>
                  </div>
                </div>

                {/* 댓글 스레드 */}
                {replies.length > 0 && (
                  <div style={{ borderTop: '1px solid #edeff1', padding: '8px 8px 8px 44px' }}>
                    {replies.map((reply, ri) => (
                      <div key={reply.id} className="post-item" style={{
                        borderLeft: '2px solid #edeff1', paddingLeft: 10, marginBottom: 8,
                        animationDelay: `${(i * 60) + (ri + 1) * 80}ms`,
                      }}>
                        <div style={{ fontSize: 11, color: '#878a8c', marginBottom: 3 }}>
                          <span style={{ fontWeight: 700, color: '#1c1c1c' }}>
                            u/{reply.author_name.toLowerCase().replace(/\s/g, '_')}
                          </span>
                          {' · '}{reply.upvotes} points
                        </div>
                        <p style={{ margin: '0 0 4px', fontSize: 13, color: '#1c1c1c', lineHeight: 1.5 }}>{reply.content}</p>
                        <div style={{ display: 'flex', gap: 8, fontSize: 11, color: '#878a8c' }}>
                          <span style={{ cursor: 'pointer' }}>▲ {reply.upvotes}</span>
                          <span style={{ cursor: 'pointer' }}>reply</span>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
