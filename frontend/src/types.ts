export type Platform =
  | 'hackernews'
  | 'producthunt'
  | 'indiehackers'
  | 'reddit_startups'
  | 'linkedin'

export type Provider = 'openai' | 'anthropic' | 'gemini'

export interface SimConfig {
  input_text: string
  language: string
  num_rounds: number
  max_agents: number
  platforms: Platform[]
  activation_rate: number
  source_limits: Record<string, number>
  provider: Provider
}

export interface SocialPost {
  id: string
  platform: Platform
  author_node_id: string
  author_name: string
  content: string
  action_type: string
  round_num: number
  upvotes: number
  downvotes: number
  parent_id: string | null
}

export interface Persona {
  node_id: string
  name: string
  role: string
  mbti: string
  bias: string
  interests: string[]
}

export interface ReportSegment {
  name: string
  sentiment: 'positive' | 'neutral' | 'negative'
  summary: string
  key_quotes: string[]
}

export interface CriticismCluster {
  theme: string
  count: number
  examples: string[]
}

export interface Improvement {
  suggestion: string
  frequency: number
}

export interface ReportJSON {
  verdict: 'positive' | 'mixed' | 'skeptical' | 'negative'
  evidence_count: number
  segments: ReportSegment[]
  criticism_clusters: CriticismCluster[]
  improvements: Improvement[]
}

export interface SourceItem {
  id: string
  title: string
  source: string
  score: number
  url?: string
  text?: string
  date?: string
  metadata?: Record<string, unknown>
}

export interface SimResults {
  sim_id: string
  posts_json: Partial<Record<Platform, SocialPost[]>>
  personas_json: Partial<Record<Platform, Persona[]>>
  report_json: ReportJSON
  report_md: string
  analysis_md: string
  sources_json: SourceItem[]
  final_report_md: string
  context_nodes_json: ContextGraphNode[]
}

export interface HistoryItem {
  id: string
  created_at: string
  input_text_snippet: string
  language: string
  config: SimConfig & { provider?: Provider }
  status: 'running' | 'completed' | 'failed'
  domain: string
}

// ── Ontology types ────────────────────────────────────────────────────────────

export interface OntologyEntity {
  id: string            // "e0", "e1", ...
  name: string
  type: string          // framework | product | company | technology | concept | market_segment | pain_point | research | standard | regulation
  source_node_ids: string[]
}

export interface OntologyRelationship {
  from: string          // entity id
  to: string            // entity id
  type: string          // competes_with | integrates_with | built_on | targets | addresses | enables | regulated_by | part_of
}

export interface OntologyData {
  domain_summary: string
  entities: OntologyEntity[]
  relationships: OntologyRelationship[]
  market_tensions: string[]
  key_trends: string[]
}

// ── Context Graph types ────────────────────────────────────────────────────────

export interface ContextGraphNode {
  id: string
  title: string
  source: string
  url: string
}

export interface ContextGraphEdge {
  source: string
  target: string
  weight: number
  label: string
}

export interface ContextGraphData {
  nodes: ContextGraphNode[]
  edges: ContextGraphEdge[]
}
