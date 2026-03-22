import { useEffect, useRef, useState } from 'react'
import type { Platform, SocialPost, ContextGraphData, ContextGraphNode, ContextGraphEdge } from '../types'

export type SourceItem = { source: string; title: string; snippet: string }

export type SimEvent =
  | { type: 'sim_start'; agent_count: number }
  | { type: 'sim_progress'; message: string }
  | { type: 'sim_source_item'; source: string; title: string; snippet: string }
  | { type: 'sim_analysis'; data: { markdown: string } }
  | { type: 'sim_graph_node'; node: ContextGraphNode }
  | { type: 'sim_graph_edges'; edges: ContextGraphEdge[] }
  | { type: 'sim_persona'; name: string; role: string; platform: Platform }
  | { type: 'sim_platform_post'; post: SocialPost }
  | { type: 'sim_round_summary'; round_num: number }
  | { type: 'sim_report'; data: Record<string, unknown> }
  | { type: 'sim_warning'; message: string }
  | { type: 'sim_error'; message: string }
  | { type: 'sim_done' }
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
  lastRound: number
  backendStatus: string | null
  canResume: boolean
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
    lastRound: 0,
    backendStatus: null,
    canResume: false,
  }
}

export function useSimulation(simId: string): UseSimulationResult {
  const [state, setState] = useState<SimState>(createInitialState)
  const [connectionKey, setConnectionKey] = useState(0)
  const lastEventIdRef = useRef<string>('0')

  useEffect(() => {
    setState(createInitialState())
    lastEventIdRef.current = '0'
  }, [simId])

  useEffect(() => {
    if (!simId) return
    const API_BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'
    const RECONNECT_DELAYS = [1000, 2000, 4000, 8000, 16000, 30000]
    const MAX_RETRIES = RECONNECT_DELAYS.length
    let retryCount = 0
    let stopped = false
    let currentEs: EventSource | null = null

    function connect() {
      if (stopped) return
      const lastId = lastEventIdRef.current
      const url = lastId !== '0'
        ? `${API_BASE}/simulate-stream/${simId}?last_id=${encodeURIComponent(lastId)}`
        : `${API_BASE}/simulate-stream/${simId}`
      const es = new EventSource(url)
      currentEs = es

      es.onmessage = (e) => {
        let event: SimEvent
        try {
          event = JSON.parse(e.data) as SimEvent
        } catch {
          return
        }
        if (event.type === 'heartbeat') return

        retryCount = 0
        if (e.lastEventId) lastEventIdRef.current = e.lastEventId

        setState(prev => {
          const next = { ...prev, events: [...prev.events, event] }
          if (event.type === 'sim_start') {
            next.status = 'running'
            next.agentCount = event.agent_count
            next.errorMsg = ''
            next.isSourcing = false
            next.backendStatus = 'running'
            next.canResume = false
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
          } else if (event.type === 'sim_platform_post') {
            const platform = event.post.platform
            const posts = { ...prev.postsByPlatform }
            posts[platform] = [...(posts[platform] || []), event.post]
            next.postsByPlatform = posts
          } else if (event.type === 'sim_round_summary') {
            next.roundNum = event.round_num
          } else if (event.type === 'sim_persona') {
            next.personaCount = prev.personaCount + 1
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
            next.report = (event.data as Record<string, unknown>).report_json as Record<string, unknown>
            next.personas = (event.data as Record<string, unknown>).personas as Record<string, unknown>
          } else if (event.type === 'sim_progress') {
            if (event.message.toLowerCase().includes('searching') ||
                event.message.toLowerCase().includes('sources') ||
                event.message.toLowerCase().includes('structurizing')) {
              next.isSourcing = true
            }
          } else if (event.type === 'sim_error') {
            next.status = 'error'
            next.errorMsg = event.message
          } else if (event.type === 'sim_done') {
            if (prev.status !== 'error') next.status = 'done'
            stopped = true
            es.close()
          }
          return next
        })
      }

      es.onerror = () => {
        es.close()
        if (stopped) return
        if (retryCount >= MAX_RETRIES) {
          setState(prev => ({ ...prev, status: 'error', errorMsg: 'Connection lost' }))
          return
        }
        const delay = RECONNECT_DELAYS[retryCount]
        retryCount++
        window.setTimeout(connect, delay)
      }
    }

    connect()
    return () => {
      stopped = true
      currentEs?.close()
    }
  }, [simId, connectionKey])

  useEffect(() => {
    if (state.status !== 'error' || !simId) return
    const API_BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'
    let cancelled = false
    let retryTimer: number | null = null

    const checkStatus = () => {
      fetch(`${API_BASE}/simulate/${simId}/status`)
        .then(r => r.ok ? r.json() : null)
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
            retryTimer = window.setTimeout(checkStatus, 1500)
          }
        })
        .catch(() => {})
    }

    checkStatus()
    return () => {
      cancelled = true
      if (retryTimer !== null) window.clearTimeout(retryTimer)
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
