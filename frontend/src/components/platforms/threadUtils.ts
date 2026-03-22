import type { SocialPost } from '../../types'

export interface ThreadedPosts {
  topLevel: SocialPost[]
  getReplies: (parentId: string) => SocialPost[]
}

export function getThreadedPosts(posts: SocialPost[]): ThreadedPosts {
  const topLevel: SocialPost[] = []
  const repliesByParent = new Map<string, SocialPost[]>()

  for (const post of posts) {
    const parentId = post.parent_id

    // Preserve the previous component behavior:
    // only posts without a truthy parent_id are treated as top-level.
    if (!parentId) {
      topLevel.push(post)
      continue
    }

    const replies = repliesByParent.get(parentId)
    if (replies) {
      replies.push(post)
      continue
    }

    repliesByParent.set(parentId, [post])
  }

  return {
    topLevel,
    getReplies: (id: string) => repliesByParent.get(id) ?? []
  }
}
