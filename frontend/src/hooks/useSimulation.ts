import { useEffect, useRef, useState } from 'react'
import { API_BASE } from '../api'
import type { Platform, Persona, SocialPost, ContextGraphData, ContextGraphNode, ContextGraphEdge } from '../types'

export type SourceItem = { source: string; title: string; snippet: string }

export type SimEvent =
  | { type: 'sim_start'; agent_count: number }
  | { type: 'sim_progress'; message: string; early_exit?: boolean }
  | { type: 'sim_source_item'; source: string; title: string; snippet: string }
  | { type: 'sim_analysis'; data: { markdown: string } }
  | { type: 'sim_graph_node'; node: ContextGraphNode }
  | { type: 'sim_graph_edges'; edges: ContextGraphEdge[] }
  | { type: 'sim_persona'; name?: string; role?: string; platform: Platform; mbti?: string; bias?: string; interests?: string[]; age?: number; seniority?: string; affiliation?: string; company?: string; skepticism?: number; commercial_focus?: number; innovation_openness?: number; source_title?: string; domain_type?: string; tech_area?: string[]; market?: string[]; problem_domain?: string[]; jtbd?: string; cognitive_pattern?: string; emotional_state?: string; generation?: string; persona?: Partial<Persona> }
  | { type: 'sim_platform_post'; post: SocialPost }
  | { type: 'sim_platform_reaction'; platform: Platform; post_id: string; reaction_type: string; actor_name: string; new_upvotes: number; new_downvotes: number }
  | { type: 'sim_round_summary'; round_num: number; platform_summaries?: Record<string, { active_agents?: number; new_posts?: number; new_comments?: number; new_votes?: number }>; segment_distribution?: Record<string, number>; action_type_distribution?: Record<string, number>; pass_count?: number; inactive_count?: number; convergence_score?: number }
  | { type: 'sim_report'; data: Record<string, unknown> }
  | { type: 'sim_gtm_report'; data: { markdown: string } }
  | { type: 'sim_final_report'; data: { markdown: string } }
  | { type: 'sim_warning'; message: string }
  | { type: 'sim_error'; message: string }
  | { type: 'sim_done' }
  | { type: 'sim_eta'; eta_seconds: number; elapsed_seconds: number; completed_rounds: number; total_rounds: number }
  | { type: 'sim_early_stop'; stopped_at_round: number; convergence_score: number }
  | { type: 'sim_resume'; from_round: number }
  | { type: 'heartbeat' }

export interface SimState {
  status: 'connecting' | 'running' | 'done' | 'error'
  events: SimEvent[]
  postsByPlatform: Partial<Record<Platform, SocialPost[]>>
  report: Record<string, unknown> | null
  personas: Record<string, unknown> | null
  analysisMd: string
  errorMsg: string
  roundNum: number
  agentCount: number
  personaCount: number
  sourceTimeline: SourceItem[]
  graphData: ContextGraphData | null
  isSourcing: boolean
  streamingPersonas: Partial<Record<string, Persona[]>>
  roundStats: Array<{ round: number; totalActiveAgents: number; totalNewPosts: number; totalNewComments: number; pass_count?: number; inactive_count?: number; convergence_score?: number }>
  lastRound: number
  backendStatus: string | null
  canResume: boolean
  warnings: string[]
  liveSentiment: { positive: number; neutral: number; negative: number }
  eta?: { etaSeconds: number; elapsedSeconds: number; completedRounds: number; totalRounds: number }
  segmentDistribution?: Record<string, number>
  earlyStop: { stoppedAtRound: number; convergenceScore: number } | null
  personaGenPhase: boolean
}

export type UseSimulationResult = SimState & {
  reconnect: () => void
}

function createInitialState(): SimState {
  return {
    status: 'connecting',
    events: [],
    postsByPlatform: {},
    report: null,
    personas: null,
    analysisMd: '',
    errorMsg: '',
    roundNum: 0,
    agentCount: 0,
    personaCount: 0,
    sourceTimeline: [],
    graphData: null,
    isSourcing: false,
    streamingPersonas: {},
    roundStats: [],
    lastRound: 0,
    backendStatus: null,
    canResume: false,
    warnings: [],
    liveSentiment: { positive: 0, neutral: 0, negative: 0 },
    earlyStop: null,
    personaGenPhase: false,
  }
}

export function useSimulation(simId: string): UseSimulationResult {
  const [state, setState] = useState<SimState>(createInitialState)
  const [connectionKey, setConnectionKey] = useState(0)
  const lastEventIdRef = useRef<string>('0')
  const postQueueRef = useRef<SocialPost[]>([])
  const drainTimerRef = useRef<number | null>(null)

  function scheduleDrain() {
    if (drainTimerRef.current !== null) return
    drainTimerRef.current = window.setTimeout(function drain() {
      drainTimerRef.current = null
      const post = postQueueRef.current.shift()
      if (!post) return
      setState(prev => {
        const posts = { ...prev.postsByPlatform }
        posts[post.platform] = [...(posts[post.platform] || []), post]
        return { ...prev, postsByPlatform: posts }
      })
      if (postQueueRef.current.length > 0) {
        drainTimerRef.current = window.setTimeout(drain, 200)
      }
    }, 200)
  }

  useEffect(() => {
    setState(createInitialState())
    lastEventIdRef.current = '0'
    postQueueRef.current = []
    if (drainTimerRef.current !== null) {
      window.clearTimeout(drainTimerRef.current)
      drainTimerRef.current = null
    }
  }, [simId])

  useEffect(() => {
    if (!simId) return
    const RECONNECT_DELAYS = [1000, 2000, 4000, 8000, 16000, 30000]
    const MAX_RETRIES = RECONNECT_DELAYS.length
    let retryCount = 0
    let stopped = false
    let currentEs: EventSource | null = null
    let reconnectTimer: number | null = null

    function connect() {
      if (stopped) return
      if (reconnectTimer !== null) {
        window.clearTimeout(reconnectTimer)
        reconnectTimer = null
      }

      const lastId = lastEventIdRef.current
      const url = lastId !== '0'
        ? `${API_BASE}/simulate-stream/${simId}?last_id=${encodeURIComponent(lastId)}`
        : `${API_BASE}/simulate-stream/${simId}`
      const es = new EventSource(url)
      currentEs = es

      es.onmessage = (e) => {
        if (currentEs !== es) return

        let event: SimEvent
        try {
          event = JSON.parse(e.data) as SimEvent
        } catch {
          return
        }
        if (event.type === 'heartbeat') return

        retryCount = 0
        if (e.lastEventId) lastEventIdRef.current = e.lastEventId

        if (event.type === 'sim_platform_post') {
          postQueueRef.current.push(event.post)
          scheduleDrain()
          // Update live sentiment counters
          const s = event.post.sentiment
          if (s === 'positive' || s === 'neutral' || s === 'negative') {
            setState(prev => ({
              ...prev,
              liveSentiment: {
                ...prev.liveSentiment,
                [s]: prev.liveSentiment[s] + 1,
              },
            }))
          }
          return
        }

        if (event.type === 'sim_platform_reaction') {
          const queueIdx = postQueueRef.current.findIndex(p => p.id === event.post_id)
          if (queueIdx !== -1) {
            postQueueRef.current[queueIdx] = {
              ...postQueueRef.current[queueIdx],
              upvotes: event.new_upvotes,
              downvotes: event.new_downvotes,
            }
          } else {
            setState(prev => {
              const platformPosts = prev.postsByPlatform[event.platform]
              if (!platformPosts) return prev
              const idx = platformPosts.findIndex(p => p.id === event.post_id)
              if (idx === -1) return prev
              const updated = [...platformPosts]
              updated[idx] = { ...updated[idx], upvotes: event.new_upvotes, downvotes: event.new_downvotes }
              return { ...prev, postsByPlatform: { ...prev.postsByPlatform, [event.platform]: updated } }
            })
          }
          return
        }

        setState(prev => {
          const next = { ...prev, events: [...prev.events, event] }
          if (event.type === 'sim_start') {
            next.status = 'running'
            next.agentCount = event.agent_count
            next.errorMsg = ''
            next.isSourcing = false
            next.backendStatus = 'running'
            next.canResume = false
            next.personaGenPhase = true
          } else if (event.type === 'sim_resume') {
            next.status = 'running'
            next.errorMsg = ''
            next.isSourcing = false
            next.backendStatus = 'running'
            next.canResume = false
            next.lastRound = Math.max(prev.lastRound, event.from_round - 1)
          } else if (event.type === 'sim_source_item') {
            next.isSourcing = true
            next.sourceTimeline = [
              { source: event.source, title: event.title, snippet: event.snippet },
              ...prev.sourceTimeline,
            ]
          } else if (event.type === 'sim_round_summary') {
            next.personaGenPhase = false
            next.roundNum = event.round_num
            if (event.platform_summaries) {
              let totalActiveAgents = 0
              let totalNewPosts = 0
              let totalNewComments = 0
              for (const stats of Object.values(event.platform_summaries)) {
                totalActiveAgents += stats.active_agents ?? 0
                totalNewPosts += stats.new_posts ?? 0
                totalNewComments += stats.new_comments ?? 0
              }
              next.roundStats = [...prev.roundStats, {
                round: event.round_num,
                totalActiveAgents,
                totalNewPosts,
                totalNewComments,
                pass_count: event.pass_count,
                inactive_count: event.inactive_count,
                convergence_score: event.convergence_score,
              }]
            }
            if (event.segment_distribution) {
              next.segmentDistribution = event.segment_distribution
            }
          } else if (event.type === 'sim_persona') {
            next.personaCount = prev.personaCount + 1
            const platform = event.platform as string
            const p = event.persona ?? event
            const persona: Persona = {
              node_id: `persona-${prev.personaCount}`,
              name: p.name ?? '',
              role: p.role ?? '',
              mbti: p.mbti ?? '',
              interests: p.interests ?? [],
              bias: p.bias,
              age: p.age,
              seniority: p.seniority,
              affiliation: p.affiliation,
              company: p.company,
              skepticism: p.skepticism,
              commercial_focus: p.commercial_focus,
              innovation_openness: p.innovation_openness,
              source_title: p.source_title,
              domain_type: p.domain_type,
              tech_area: p.tech_area,
              market: p.market,
              problem_domain: p.problem_domain,
              jtbd: p.jtbd,
              cognitive_pattern: p.cognitive_pattern,
              emotional_state: p.emotional_state,
              generation: p.generation,
            }
            next.streamingPersonas = {
              ...prev.streamingPersonas,
              [platform]: [...(prev.streamingPersonas[platform] ?? []), persona],
            }
          } else if (event.type === 'sim_analysis') {
            next.analysisMd = event.data.markdown
          } else if (event.type === 'sim_graph_node') {
            next.graphData = {
              nodes: [...(prev.graphData?.nodes ?? []), event.node],
              edges: prev.graphData?.edges ?? [],
            }
          } else if (event.type === 'sim_graph_edges') {
            next.graphData = {
              nodes: prev.graphData?.nodes ?? [],
              edges: [...(prev.graphData?.edges ?? []), ...event.edges],
            }
          } else if (event.type === 'sim_report') {
            next.report = ((event.data as Record<string, unknown>).report_json as Record<string, unknown>) ?? null
            next.personas = (event.data as Record<string, unknown>).personas as Record<string, unknown>
          } else if (event.type === 'sim_progress') {
            if (event.message.toLowerCase().includes('searching') ||
                event.message.toLowerCase().includes('sources') ||
                event.message.toLowerCase().includes('structurizing')) {
              next.isSourcing = true
            }
          } else if (event.type === 'sim_eta') {
            next.eta = {
              etaSeconds: event.eta_seconds,
              elapsedSeconds: event.elapsed_seconds,
              completedRounds: event.completed_rounds,
              totalRounds: event.total_rounds,
            }
          } else if (event.type === 'sim_early_stop') {
            next.earlyStop = {
              stoppedAtRound: event.stopped_at_round,
              convergenceScore: event.convergence_score,
            }
          } else if (event.type === 'sim_warning') {
            next.warnings = [...prev.warnings, event.message]
          } else if (event.type === 'sim_error') {
            next.status = 'error'
            next.errorMsg = event.message
          } else if (event.type === 'sim_done') {
            if (prev.status !== 'error') next.status = 'done'
          }
          return next
        })

        if (event.type === 'sim_done') {
          stopped = true
          if (reconnectTimer !== null) {
            window.clearTimeout(reconnectTimer)
            reconnectTimer = null
          }
          if (currentEs === es) currentEs = null
          es.close()
        }
      }

      es.onerror = () => {
        if (currentEs !== es) return

        currentEs = null
        es.close()
        if (stopped) return
        if (retryCount >= MAX_RETRIES) {
          setState(prev => ({ ...prev, status: 'error', errorMsg: 'Connection lost' }))
          return
        }
        const delay = RECONNECT_DELAYS[retryCount]
        retryCount++
        reconnectTimer = window.setTimeout(() => {
          reconnectTimer = null
          connect()
        }, delay)
      }
    }

    connect()
    return () => {
      stopped = true
      if (reconnectTimer !== null) window.clearTimeout(reconnectTimer)
      currentEs?.close()
      currentEs = null
      if (drainTimerRef.current !== null) {
        window.clearTimeout(drainTimerRef.current)
        drainTimerRef.current = null
      }
    }
  }, [simId, connectionKey])

  useEffect(() => {
    if (state.status !== 'error' || !simId) return
    let cancelled = false
    let retryTimer: number | null = null
    let retryCount = 0
    const MAX_STATUS_RETRIES = 10
    const controller = new AbortController()

    const checkStatus = () => {
      if (cancelled || controller.signal.aborted) return

      fetch(`${API_BASE}/simulate/${simId}/status`, { signal: controller.signal })
        .then(async r => {
          if (r.ok) return r.json()
          if (r.status === 404) return null
          throw new Error(`Status check failed: ${r.status}`)
        })
        .then(data => {
          if (cancelled || !data) return
          setState(prev => ({
            ...prev,
            status: data.status === 'completed' ? 'done' : prev.status,
            lastRound: data.last_round ?? 0,
            backendStatus: data.status ?? null,
            canResume: data.status === 'failed' && (data.last_round ?? 0) > 0,
          }))
          if (!cancelled && data.status === 'running') {
            if (retryCount >= MAX_STATUS_RETRIES) return
            retryCount++
            retryTimer = window.setTimeout(() => {
              retryTimer = null
              checkStatus()
            }, Math.min(1500 * retryCount, 15000))
          }
        })
        .catch(error => {
          if (cancelled || controller.signal.aborted) return
          if (error instanceof DOMException && error.name === 'AbortError') return
          if (error?.name === 'AbortError') return
          if (retryCount >= MAX_STATUS_RETRIES) return
          retryCount++
          retryTimer = window.setTimeout(() => {
            retryTimer = null
            checkStatus()
          }, Math.min(1500 * retryCount, 15000))
        })
    }

    checkStatus()
    return () => {
      cancelled = true
      if (retryTimer !== null) window.clearTimeout(retryTimer)
      controller.abort()
    }
  }, [state.status, simId])

  const reconnect = () => {
    setState(prev => ({
      ...prev,
      status: 'connecting',
      errorMsg: '',
      backendStatus: 'running',
      canResume: false,
    }))
    setConnectionKey(prev => prev + 1)
  }

  return {
    ...state,
    reconnect,
  }
}
