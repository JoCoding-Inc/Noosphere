import type { SocialPost } from '../../types'
import { getThreadedPosts } from './threadUtils'

interface Props { posts: SocialPost[]; idea?: string }

export function ProductHuntUI({ posts, idea = 'New Product' }: Props) {
  const { topLevel, getReplies } = getThreadedPosts(posts)

  // PH replies are flat (1 level only) — deeper replies appear at same indent
  function renderReplies(parentId: string, _depth: number, baseDelay: number) {
    const flat: Array<{ post: SocialPost; delay: number }> = []
    let d = baseDelay
    function collect(pid: string) {
      getReplies(pid).forEach((r, ri) => {
        d += (ri + 1) * 60
        flat.push({ post: r, delay: d })
        collect(r.id)
      })
    }
    collect(parentId)
    if (flat.length === 0) return null
    return flat.map(({ post: reply, delay }) => (
      <div key={reply.id} className="post-item" style={{
        marginLeft: 24, marginTop: 6,
        background: '#fafafa',
        border: '1px solid #efefef', borderRadius: 8, padding: '10px 14px',
        animationDelay: `${delay}ms`,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6 }}>
          <div style={{
            width: 22, height: 22, borderRadius: '50%',
            background: `hsl(${(reply.author_name.charCodeAt(0) * 53) % 360}, 55%, 60%)`,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 10, fontWeight: 700, color: '#fff', flexShrink: 0,
          }}>
            {reply.author_name[0].toUpperCase()}
          </div>
          <span style={{ fontWeight: 600, fontSize: 12, color: '#1a1a1a' }}>{reply.author_name}</span>
        </div>
        <p style={{ margin: 0, fontSize: 13, color: '#444', lineHeight: 1.5 }}>{reply.content}</p>
      </div>
    ))
  }

  const totalUpvotes = posts.reduce((s, p) => s + p.upvotes, 0)

  return (
    <div style={{ fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif' }}>
      {/* PH 헤더 카드 */}
      <div style={{
        background: '#fff', border: '1px solid #e8e8e8', borderRadius: 12,
        padding: '16px 20px', marginBottom: 12,
        display: 'flex', alignItems: 'center', gap: 16,
        boxShadow: '0 1px 4px rgba(0,0,0,0.06)',
      }}>
        {/* 업보트 버튼 */}
        <div style={{
          display: 'flex', flexDirection: 'column', alignItems: 'center',
          border: '1px solid #e8e8e8', borderRadius: 8,
          padding: '6px 12px', cursor: 'pointer', minWidth: 52,
          transition: 'all 0.15s',
        }}>
          <span style={{ fontSize: 14, color: '#da552f' }}>▲</span>
          <span style={{ fontSize: 14, fontWeight: 700, color: '#da552f' }}>{totalUpvotes}</span>
        </div>

        {/* 제품 아이콘 placeholder */}
        <div style={{
          width: 52, height: 52, borderRadius: 10,
          background: 'linear-gradient(135deg, #667eea, #764ba2)',
          flexShrink: 0,
        }} />

        {/* 제품 정보 */}
        <div style={{ flex: 1 }}>
          <div style={{ fontWeight: 700, fontSize: 16, color: '#1a1a1a', marginBottom: 2 }}>{idea.slice(0, 40)}</div>
          <div style={{ color: '#6e6e6e', fontSize: 13 }}>AI-powered market simulation · {posts.length} discussions</div>
          <div style={{ display: 'flex', gap: 6, marginTop: 6 }}>
            {['AI', 'Developer Tools', 'Productivity'].map(tag => (
              <span key={tag} style={{
                fontSize: 11, padding: '2px 8px', borderRadius: 12,
                background: '#f5f5f5', color: '#6e6e6e', border: '1px solid #e8e8e8',
              }}>{tag}</span>
            ))}
          </div>
        </div>
      </div>

      {/* 댓글 피드 */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        {topLevel.length === 0 && (
          <div style={{ textAlign: 'center', color: '#999', fontSize: 13, padding: 20 }}>
            Waiting for reviews...
          </div>
        )}
        {topLevel.map((post, i) => {
          return (
            <div key={post.id} className="post-item" style={{ animationDelay: `${i * 60}ms` }}>
              <div style={{
                background: '#fff', border: '1px solid #e8e8e8', borderRadius: 10,
                padding: '12px 16px', boxShadow: '0 1px 3px rgba(0,0,0,0.04)',
              }}>
                {/* 작성자 */}
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                  <div style={{
                    width: 30, height: 30, borderRadius: '50%',
                    background: `hsl(${(post.author_name.charCodeAt(0) * 37) % 360}, 60%, 65%)`,
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    fontSize: 12, fontWeight: 700, color: '#fff', flexShrink: 0,
                  }}>
                    {post.author_name[0].toUpperCase()}
                  </div>
                  <div>
                    <div style={{ fontWeight: 600, fontSize: 13, color: '#1a1a1a' }}>{post.author_name}</div>
                    <div style={{ fontSize: 11, color: '#999' }}>{post.upvotes} helpful</div>
                  </div>
                </div>
                <p style={{ margin: 0, fontSize: 14, color: '#333', lineHeight: 1.6 }}>{post.content}</p>

                {/* 반응 바 */}
                <div style={{ display: 'flex', gap: 12, marginTop: 10 }}>
                  <button style={{
                    background: 'none', border: 'none', cursor: 'pointer',
                    fontSize: 12, color: '#da552f', padding: 0, fontWeight: 600,
                  }}>▲ Upvote</button>
                  <button style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 12, color: '#999', padding: 0 }}>
                    Reply
                  </button>
                </div>
              </div>

              {/* 답글 (재귀) */}
              {renderReplies(post.id, 1, i * 60)}
            </div>
          )
        })}
      </div>
    </div>
  )
}
