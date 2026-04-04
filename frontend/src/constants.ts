import type { Platform, ReportJSON } from './types'
import { t } from './tokens'

export const SOURCE_COLORS: Record<string, string> = {
  arxiv:            '#7B2D8E', // 짙은 보라
  semantic_scholar: '#1D4ED8', // 로열 블루
  hackernews:       '#FF6B35', // 주황
  reddit:           '#C5283D', // 크림슨
  github:           '#15803D', // 포레스트 그린
  product_hunt:     '#EC4899', // 핫핑크
  itunes:           '#F59E0B', // 앰버
  google_play:      '#14B8A6', // 틸
  gdelt:            '#84CC16', // 라임
  serper:           '#0891B2', // 시안
  input_text:       '#64748B', // 슬레이트 그레이
  idea:             '#A855F7', // 바이올렛
}

export const PLATFORM_COLORS: Record<Platform, string> = {
  hackernews:      '#f97316',
  producthunt:     '#ef4444',
  indiehackers:    '#8b5cf6',
  reddit_startups: '#b45309',
  linkedin:        '#2563eb',
}

export const PLATFORM_OPTIONS: Array<{ id: Platform; label: string; description: string }> = [
  { id: 'hackernews',      label: 'Hacker News',      description: 'Technical founders & engineers' },
  { id: 'producthunt',     label: 'Product Hunt',     description: 'Early adopters & makers' },
  { id: 'indiehackers',    label: 'Indie Hackers',    description: 'Bootstrappers & solo founders' },
  { id: 'reddit_startups', label: 'Reddit r/startups', description: 'Broad startup community' },
  { id: 'linkedin',        label: 'LinkedIn',         description: 'Professionals & executives' },
]

type VerdictConfig = { color: string; label: string; icon: string }

export const VERDICT_CONFIG: Record<ReportJSON['verdict'], VerdictConfig> = {
  positive:  { color: '#22c55e', label: 'Positive',  icon: '<path d="M20 6L9 17l-5-5" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>' },
  mixed:     { color: '#f59e0b', label: 'Mixed',     icon: '<path d="M5 12h14M5 8h14M5 16h8" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>' },
  skeptical: { color: t.color.orange, label: 'Skeptical', icon: '<circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="2"/><path d="M12 8v4M12 16h.01" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>' },
  negative:  { color: '#ef4444', label: 'Negative',  icon: '<path d="M18 6L6 18M6 6l12 12" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"/>' },
}
