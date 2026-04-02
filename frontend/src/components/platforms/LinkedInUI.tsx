import type { SocialPost } from '../../types'
import { getThreadedPosts } from './threadUtils'
import { ThreadCollapseButton, type ThreadCollapseProps } from './ThreadCollapseButton'

interface Props extends ThreadCollapseProps { posts: SocialPost[] }

const REACTIONS = ['👍', '❤️', '🙌', '💡', '🤔']
const HASHTAG_POOL = ['#AI', '#Founders', '#ProductValidation', '#StartupLife', '#BuildInPublic', '#GTM', '#IndieHackers', '#MVP', '#ProductDevelopment']

function liGradient(name: string, mul: number, offset: number, l1: number, l2: number) {
  const h1 = ((name.charCodeAt(0) || 65) * mul) % 360
  const h2 = ((name.charCodeAt(0) || 65) * mul + offset) % 360
  return `linear-gradient(135deg, hsl(${h1}, 55%, ${l1}%), hsl(${h2}, 55%, ${l2}%))`
}

function getHashtags(content: string): string[] {
  const lower = content.toLowerCase()
  const tags: string[] = []
  if (lower.includes('ai') || lower.includes('llm')) tags.push('#AI')
  if (lower.includes('founder') || lower.includes('startup')) tags.push('#Founders')
  if (lower.includes('validat') || lower.includes('product')) tags.push('#ProductValidation')
  if (lower.includes('gtm') || lower.includes('launch')) tags.push('#GTM')
  if (lower.includes('build') || lower.includes('indie')) tags.push('#BuildInPublic')
  if (tags.length === 0) tags.push(HASHTAG_POOL[content.length % HASHTAG_POOL.length], '#Founders')
  return tags.slice(0, 3)
}

export function LinkedInUI({ posts, collapsibleThreads, expandedThreads, onToggleThread }: Props) {
  const { topLevel, getReplies } = getThreadedPosts(posts)

  // LinkedIn: fully flat comments — all replies at same level, no indentation, @mention for context
  function renderComments(parentId: string, parentAuthor: string) {
    const flat: Array<{ post: SocialPost; replyTo: string; idx: number }> = []
    let idx = 0
    function collectFlat(pid: string, replyToName: string) {
      for (const r of getReplies(pid)) {
        flat.push({ post: r, replyTo: replyToName, idx: idx++ })
        collectFlat(r.id, r.author_name)
      }
    }
    collectFlat(parentId, parentAuthor)
    if (flat.length === 0) return null

    return (
      <div style={{ padding: '0 16px 8px', borderTop: '1px solid rgba(0,0,0,0.06)' }}>
        {flat.map(({ post: reply, replyTo, idx: i }) => {
          const avatarBg = liGradient(reply.author_name, 53, 60, 60, 50)
          return (
            <div key={reply.id} className="post-item" style={{ display: 'flex', gap: 8, paddingTop: 10, animationDelay: `${(i + 1) * 80}ms` }}>
              <div style={{
                width: 32, height: 32, borderRadius: '50%', flexShrink: 0,
                background: avatarBg,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: 12, fontWeight: 700, color: '#fff',
              }}>
                {(reply.author_name?.[0] ?? '?').toUpperCase()}
              </div>
              <div style={{ flex: 1 }}>
                <div style={{ background: '#f2f2f2', borderRadius: '0 8px 8px 8px', padding: '8px 12px' }}>
                  <div style={{ fontWeight: 600, fontSize: 13, color: 'rgba(0,0,0,0.9)', marginBottom: 3 }}>{reply.author_name}</div>
                  <p style={{ margin: 0, fontSize: 13, color: 'rgba(0,0,0,0.8)', lineHeight: 1.5 }}>
                    <span style={{ color: '#0a66c2', fontWeight: 600 }}>@{replyTo} </span>
                    {reply.content}
                  </p>
                </div>
                <div style={{ fontSize: 11, color: 'rgba(0,0,0,0.45)', marginTop: 4, paddingLeft: 2 }}>
                  Like · Reply
                </div>
              </div>
            </div>
          )
        })}
      </div>
    )
  }

  return (
    <div style={{ fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif', background: '#f3f2ef', padding: '0', borderRadius: 8 }}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {topLevel.length === 0 && (
          <div style={{ background: '#fff', borderRadius: 8, padding: '24px', textAlign: 'center', color: '#666', fontSize: 14 }}>
            No posts yet...
          </div>
        )}
        {topLevel.map((post, i) => {
          const replies = getReplies(post.id)
          const postBg = liGradient(post.author_name, 47, 60, 55, 45)
          const hashtags = getHashtags(post.content)

          return (
            <div key={post.id} className="post-item" style={{
              background: '#fff', borderRadius: 8,
              border: '1px solid rgba(0,0,0,0.08)',
              boxShadow: '0 0 0 1px rgba(0,0,0,0.04)',
              overflow: 'hidden',
              animationDelay: `${i * 60}ms`,
            }}>
              {/* Author header */}
              <div style={{ padding: '12px 16px 0', display: 'flex', gap: 10, alignItems: 'flex-start' }}>
                <div style={{
                  width: 48, height: 48, borderRadius: '50%', flexShrink: 0,
                  background: postBg,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: 18, fontWeight: 700, color: '#fff',
                }}>
                  {(post.author_name?.[0] ?? '?').toUpperCase()}
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

              {/* Post content + hashtags */}
              <div style={{ padding: '10px 16px 8px' }}>
                <p style={{ margin: '0 0 8px', fontSize: 14, color: 'rgba(0,0,0,0.9)', lineHeight: 1.6, whiteSpace: 'pre-line' }}>
                  {post.content}
                </p>
                <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                  {hashtags.map(tag => (
                    <span key={tag} style={{ fontSize: 13, color: '#0a66c2', cursor: 'pointer' }}>{tag}</span>
                  ))}
                </div>
              </div>

              {/* Reaction count */}
              <div style={{ padding: '0 16px 8px', display: 'flex', justifyContent: 'space-between', fontSize: 12, color: 'rgba(0,0,0,0.6)' }}>
                <span>
                  {REACTIONS.slice(0, 3).join('')} {post.upvotes + 12}
                </span>
                <span>{replies.length} comments</span>
              </div>

              {/* Action bar */}
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

              {/* Thread collapse/expand */}
              <div style={{ padding: '0 16px' }}>
                <ThreadCollapseButton
                  postId={post.id}
                  collapsibleThreads={collapsibleThreads}
                  expandedThreads={expandedThreads}
                  onToggleThread={onToggleThread}
                />
              </div>

              {/* Flat @mention comment section */}
              {renderComments(post.id, post.author_name)}
            </div>
          )
        })}
      </div>
    </div>
  )
}
