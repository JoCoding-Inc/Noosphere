import type { SocialPost } from '../../types'
import { getThreadedPosts } from './threadUtils'

interface Props { posts: SocialPost[] }

export function HackerNewsUI({ posts }: Props) {
  const { topLevel, getReplies } = getThreadedPosts(posts)

  return (
    <div style={{ fontFamily: 'Verdana, Geneva, sans-serif', fontSize: 13 }}>
      {/* HN 헤더 */}
      <div style={{
        background: '#ff6600', padding: '4px 8px',
        display: 'flex', alignItems: 'center', gap: 8,
        borderRadius: '6px 6px 0 0', marginBottom: 0,
      }}>
        <span style={{ fontWeight: 700, color: '#fff', border: '1px solid #fff', padding: '1px 4px', fontSize: 12 }}>Y</span>
        <span style={{ color: '#fff', fontWeight: 700, fontSize: 13 }}>Hacker News</span>
        <span style={{ color: 'rgba(255,255,255,0.7)', fontSize: 11, marginLeft: 8 }}>new | past | comments | ask | show | jobs | submit</span>
      </div>

      <div style={{ background: '#f6f6ef', padding: '8px 4px', borderRadius: '0 0 6px 6px' }}>
        {topLevel.length === 0 && (
          <div style={{ padding: '20px', textAlign: 'center', color: '#828282', fontSize: 12 }}>
            Waiting for posts...
          </div>
        )}
        {topLevel.map((post, i) => {
          const replies = getReplies(post.id)

          return (
            <div key={post.id} className="post-item" style={{ marginBottom: 12, animationDelay: `${i * 60}ms` }}>
              {/* 포스트 행 */}
              <div style={{ display: 'flex', gap: 4, alignItems: 'flex-start', padding: '2px 4px' }}>
                <span style={{ color: '#828282', minWidth: 18, fontSize: 11, paddingTop: 1 }}>{i + 1}.</span>
                <span style={{ color: '#ff6600', fontSize: 12, cursor: 'pointer', lineHeight: 1 }}>▲</span>
                <div style={{ flex: 1 }}>
                  <div style={{ color: '#000', lineHeight: 1.5, marginBottom: 4 }}>
                    {post.content}
                  </div>
                  <div style={{ color: '#828282', fontSize: 11 }}>
                    {post.upvotes} points by{' '}
                    <span style={{ color: '#828282', textDecoration: 'underline', cursor: 'pointer' }}>{post.author_name}</span>
                    {' '}· {replies.length} comments
                  </div>
                </div>
              </div>

              {/* 댓글 */}
              {replies.map((reply, ri) => (
                <div key={reply.id} className="post-item" style={{
                  marginLeft: 36, marginTop: 6, paddingLeft: 8,
                  borderLeft: '2px solid #e4e4d8',
                  animationDelay: `${(i * 60) + (ri + 1) * 80}ms`,
                }}>
                  <div style={{ color: '#828282', fontSize: 11, marginBottom: 3 }}>
                    <span style={{ color: '#828282', textDecoration: 'underline', cursor: 'pointer' }}>{reply.author_name}</span>
                    {' '}· {reply.upvotes} points
                  </div>
                  <div style={{ color: '#2a2a2a', lineHeight: 1.5, fontSize: 13 }}>{reply.content}</div>
                </div>
              ))}
            </div>
          )
        })}
      </div>
    </div>
  )
}
