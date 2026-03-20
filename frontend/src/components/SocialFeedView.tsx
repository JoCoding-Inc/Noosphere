import type { Platform, SocialPost } from '../types'
import { PlatformSimFeed } from './PlatformSimFeed'

export function SocialFeedView({ posts }: { posts: Partial<Record<Platform, SocialPost[]>> }) {
  return <PlatformSimFeed postsByPlatform={posts} />
}
