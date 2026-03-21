import { useEffect, useState } from 'react'
import type { Platform, SocialPost, OntologyData } from '../types'

export type SourceItem = { source: string; title: string; snippet: string }

export type SimEvent =
  | { type: 'sim_start'; agent_count: number }
  | { type: 'sim_progress'; message: string }
  | { type: 'sim_source_item'; source: string; title: string; snippet: string }
  | { type: 'sim_analysis'; data: { markdown: string } }
  | { type: 'sim_ontology'; data: OntologyData }
  | { type: 'sim_persona'; name: string; role: string; platform: Platform }
  | { type: 'sim_platform_post'; post: SocialPost }
  | { type: 'sim_round_summary'; round_num: number }
  | { type: 'sim_report'; data: Record<string, unknown> }
  | { type: 'sim_warning'; message: string }
  | { type: 'sim_error'; message: string }
  | { type: 'sim_done' }

interface SimState {
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
  ontology: OntologyData | null
  isSourcing: boolean
}

export function useSimulation(simId: string): SimState {
  const [state, setState] = useState<SimState>({
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
    ontology: null,
    isSourcing: false,
  })

  useEffect(() => {
    if (!simId) return
    const API_BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'
    const es = new EventSource(`${API_BASE}/simulate-stream/${simId}`)

    es.onmessage = (e) => {
      const event: SimEvent = JSON.parse(e.data)
      setState(prev => {
        const next = { ...prev, events: [...prev.events, event] }
        if (event.type === 'sim_start') {
          next.status = 'running'
          next.agentCount = event.agent_count
        } else if (event.type === 'sim_source_item') {
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
        } else if (event.type === 'sim_ontology') {
          next.ontology = event.data
        } else if (event.type === 'sim_report') {
          next.report = (event.data as Record<string, unknown>).report_json as Record<string, unknown>
          next.personas = (event.data as Record<string, unknown>).personas as Record<string, unknown>
        } else if (event.type === 'sim_progress') {
          if (event.message.toLowerCase().includes('searching') || event.message.toLowerCase().includes('sources')) {
            next.isSourcing = true
          }
        } else if (event.type === 'sim_error') {
          next.status = 'error'
          next.errorMsg = event.message
        } else if (event.type === 'sim_done') {
          if (prev.status !== 'error') next.status = 'done'
          es.close()
        }
        return next
      })
    }

    es.onerror = () => {
      setState(prev => ({ ...prev, status: 'error', errorMsg: 'Connection lost' }))
      es.close()
    }

    return () => es.close()
  }, [simId])

  return state
}
