export type Platform =
  | 'hackernews'
  | 'producthunt'
  | 'indiehackers'
  | 'reddit_startups'
  | 'linkedin'

export interface SimConfig {
  input_text: string
  language: string
  num_rounds: number
  max_agents: number
  platforms: Platform[]
  activation_rate: number
  source_limits: Record<string, number>
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
  reply_count?: number
  vote_rounds?: number[]
  voters?: string[]
  sentiment?: 'positive' | 'neutral' | 'negative' | 'constructive' | ''
  structured_data?: Record<string, unknown>
  weighted_score?: number
}

export interface Persona {
  node_id: string
  name: string
  role: string
  mbti: string
  bias?: string
  interests: string[]
  // Backend-generated fields (optional for backward compatibility)
  age?: number
  seniority?: string          // "intern" | "junior" | "mid" | "senior" | "lead" | "principal" | "director" | "vp" | "c_suite"
  affiliation?: string        // "individual" | "startup" | "mid_size" | "enterprise" | "bigtech" | "academic"
  company?: string
  skepticism?: number         // 1-10: 1=enthusiastic evangelist, 10=extreme skeptic
  commercial_focus?: number   // 1-10: 1=idealistic/academic, 10=purely commercial
  innovation_openness?: number // 1-10: 1=very conservative, 10=early adopter
  source_title?: string
  domain_type?: string        // "tech" | "research" | "consumer" | "business" | "healthcare" | "general"
  tech_area?: string[]
  market?: string[]
  problem_domain?: string[]
  jtbd?: string               // Job-to-be-Done
  cognitive_pattern?: string   // Dominant thinking pattern
  emotional_state?: string     // Emotional context
  generation?: string          // "Gen Z" | "Millennial" | "Gen X" | "Boomer"
  region?: string
  attitude_shift?: number
  attitude_history?: Array<{round: number; delta: number; trigger_post_id: string}>
}

export interface ReportSegment {
  name: string
  sentiment: 'positive' | 'neutral' | 'negative'
  summary: string
  key_quotes: string[]
  sentiment_ratio?: string
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

export interface PraiseCluster {
  theme: string
  count: number
  examples: string[]
}

export interface PlatformSentimentSummary {
  positive: number
  neutral: number
  negative: number
  verdict: string
  total: number
  positive_pct?: number
  weighted_positive?: number
  weighted_neutral?: number
  weighted_negative?: number
  weighted_constructive?: number
  engagement_quality?: number
}

export interface SentimentTimelineEntry {
  round: number
  positive: number
  neutral: number
  negative: number
  constructive?: number
  engagement?: number
  max_depth?: number
  segment_distribution?: Record<string, number>
  action_type_distribution?: Record<string, number>
  pass_count?: number
  inactive_count?: number
}

export interface ReportJSON {
  verdict: 'positive' | 'mixed' | 'skeptical' | 'negative'
  evidence_count: number
  segments: ReportSegment[]
  praise_clusters?: PraiseCluster[]
  criticism_clusters: CriticismCluster[]
  improvements: Improvement[]
  platform_summaries?: Record<string, PlatformSentimentSummary>
  sentiment_timeline?: SentimentTimelineEntry[]
  platform_sentiment_timeline?: Record<string, Array<{round: number; positive: number; neutral: number; negative: number}>>
  adoption_score?: number
  consensus_score?: number
  response_rate?: number
  qa_response_rate?: number | null
  key_debates?: Array<{
    topic: string
    for_arguments: string[]
    against_arguments: string[]
    resolution: string
  }>
  region_sentiment?: Record<string, {
    positive: number
    neutral: number
    negative: number
    constructive: number
    total: number
    positive_pct?: number
    negative_pct?: number
  }>
  platform_segments?: Record<string, Record<string, {
    positive: number
    neutral: number
    negative: number
    total: number
    positive_pct?: number
    negative_pct?: number
    constructive_pct?: number
    effective_positive_pct?: number
  }>>
  interaction_network?: Array<{from: string; to: string; from_name?: string; to_name?: string; count: number; agree_count?: number; disagree_count?: number; from_segment?: string; to_segment?: string; sentiment_pattern?: string}>
  attitude_shifts?: Array<{
    name: string
    node_id?: string
    total_delta: number
    history: Array<{round: number; delta: number; trigger_post_id: string; trigger_summary?: string}>
  }>
  engagement_alerts?: Array<{
    round: number;
    drop_pct: number;
    prev_engagement: number;
    curr_engagement: number;
  }>;
  platform_divergence?: Array<{
    platform_a: string;
    platform_b: string;
    gap_pct: number;
    direction: string;
  }>;
  echo_chamber_risk?: Record<string, {
    entropy: number
    risk: 'low' | 'medium' | 'high'
    sentiment_homogeneity?: number
    opinion_diversity?: number
    cross_reply_polarity?: number
    dominant_sentiment?: string
  }>
  top_contributors?: Array<{
    name: string
    node_id?: string
    score: number
    posts: number
    replies_received: number
    upvotes: number
    mentions: number
    post_score?: number
    influence_score?: number
    segment?: string
  }>
  segment_attitude_shifts?: Array<{
    segment: string
    avg_delta: number
    count: number
    shifted_count: number
    confidence?: 'low' | 'medium' | 'high'
  }>
  qa_pairs?: Array<{
    question_id: string
    question_text: string
    platform: string
    author_name: string
    answers: Array<{
      text: string
      author_name: string
      upvotes: number
    }>
    answered: boolean
  }>
  convergence_round?: number | null
  early_exit_round?: number | null
  validation?: { corrections_applied: number; details: string[] }
  next_steps?: Array<{
    priority: 'P0' | 'P1' | 'P2'
    action: string
    rationale: string
    segment_impact: string[]
  }>
  segment_journey?: Record<number, Record<string, {
    positive: number
    negative: number
    neutral: number
    constructive: number
  }>>
  archetype_narratives?: Array<{
    segment: string
    journey_summary: string
    pivot_rounds: Array<{round: number; direction: string; delta_pct: number; trigger_post_snippet: string; trigger_author: string}>
    attitude_delta: number
    persona_count: number
    platform_breakdown?: Record<string, number>
  }>
  unaddressed_concerns?: Array<{
    post_id: string
    platform: string
    author_name: string
    author_segment: string
    content_snippet: string
    sentiment: string
    weighted_score: number
  }>
  environmental_influence?: {
    passive_exposure_count: number
    passive_exposure_total_delta: number
    late_joiner_count: number
    late_joiner_total_delta: number
    cross_sync_count: number
    cross_sync_total_delta: number
  }
  influence_flow?: Array<{
    influencer_name: string
    influenced_name: string
    round: number
    delta: number
    trigger_snippet: string
    influencer_segment: string
    influenced_segment: string
  }>
  debate_timeline?: Array<{
    platform: string
    root_post_id: string
    root_content_snippet: string
    author_name: string
    total_replies: number
    rounds_active: number[]
    timeline: Array<{
      round: number
      positive: number
      neutral: number
      negative: number
      constructive: number
      positive_pct: number
    }>
    turning_points: Array<{
      round: number
      direction: string
      delta_pct: number
      trigger_author?: string
      trigger_snippet?: string
    }>
    participant_segments?: Record<string, number>
  }>
  segment_conversion_funnel?: Record<string, {
    converted_positive: number
    converted_negative: number
    stayed_neutral: number
    total: number
    conversion_rate: number
    resistance_rate: number
    avg_rounds_to_convert: number | null
  }>
  producthunt_ratings?: {
    avg_rating: number
    distribution: Record<string, number>
    total_reviews: number
  }
  producthunt_pros_cons?: {
    top_pros: Array<{ theme: string; count: number }>
    top_cons: Array<{ theme: string; count: number }>
  }
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
  report_json: ReportJSON | null
  report_md: string
  analysis_md: string
  sources_json: SourceItem[]
  gtm_md: string
  final_report_md: string
  context_nodes_json: ContextGraphNode[]
}

export interface HistoryItem {
  id: string
  created_at: string
  input_text_snippet: string
  language: string
  config: SimConfig
  status: 'running' | 'completed' | 'failed' | 'partial'
  domain: string
  verdict?: string | null
  evidence_count?: number | null
  adoption_score?: number | null
  max_agents?: number | null
  duration_seconds?: number | null
  num_rounds?: number | null
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
