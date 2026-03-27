// frontend/src/components/OntologyGraph.tsx
import { useState, useCallback, useMemo, memo, useRef, useEffect } from 'react'
import ForceGraph2D, { type ForceGraphMethods, type LinkObject, type NodeObject } from 'react-force-graph-2d'
import type {
  OntologyEntity,
  OntologyRelationship,
  OntologyData,
  ContextGraphData,
  ContextGraphNode as ContextGraphDataNode,
  ContextGraphEdge as ContextGraphDataEdge,
} from '../types'
import { SOURCE_COLORS } from '../constants'

const NODE_COLORS: Record<string, string> = {
  framework:      '#3b82f6',
  product:        '#22c55e',
  company:        '#f97316',
  technology:     '#a855f7',
  market_segment: '#eab308',
  pain_point:     '#ef4444',
  research:       '#14b8a6',
  standard:       '#94a3b8',
  concept:        '#c084fc',
  regulation:     '#92400e',
}

const EDGE_COLORS: Record<string, string> = {
  competes_with:   '#ef4444',
  integrates_with: '#22c55e',
  built_on:        '#3b82f6',
  targets:         '#f97316',
  addresses:       '#14b8a6',
  enables:         '#a855f7',
  regulated_by:    '#92400e',
  part_of:         '#94a3b8',
}

const EDGE_DASHED: Record<string, boolean> = {
  competes_with: true,
  regulated_by:  true,
}

const REL_LABEL: Record<string, string> = {
  competes_with:   'competes with',
  integrates_with: 'integrates with',
  built_on:        'built on',
  targets:         'targets',
  addresses:       'addresses',
  enables:         'enables',
  regulated_by:    'regulated by',
  part_of:         'part of',
}

interface GraphNode {
  id: string
  name: string
  type: string
  source_node_ids: string[]
  color: string
}

interface GraphLinkData {
  type: string
  color: string
}

type GraphLink = LinkObject<GraphNode, GraphLinkData>

type ContextRenderNode = ContextGraphDataNode & { color: string }
type ContextRenderLinkData = Omit<ContextGraphDataEdge, 'source' | 'target'>
type ContextRenderLink = LinkObject<ContextRenderNode, ContextRenderLinkData>

type OntologyGraphHandle = ForceGraphMethods<NodeObject<GraphNode>, LinkObject<GraphNode, GraphLinkData>>
type ContextGraphHandle = ForceGraphMethods<NodeObject<ContextRenderNode>, LinkObject<ContextRenderNode, ContextRenderLinkData>>

const EMPTY_NODE_IDS: string[] = []

function hasStringProp(value: unknown, key: string): value is Record<string, string> {
  return typeof value === 'object' && value !== null && typeof (value as Record<string, unknown>)[key] === 'string'
}

function isGraphNode(node: unknown): node is GraphNode {
  return hasStringProp(node, 'id') && hasStringProp(node, 'name') && hasStringProp(node, 'type')
}

function isContextRenderNode(node: unknown): node is ContextRenderNode {
  return hasStringProp(node, 'id') && hasStringProp(node, 'title') && hasStringProp(node, 'source')
}

function isGraphLink(link: unknown): link is GraphLink {
  return (
    typeof link === 'object' &&
    link !== null &&
    'source' in link &&
    'target' in link &&
    hasStringProp(link, 'type')
  )
}

function isContextRenderLink(link: unknown): link is ContextRenderLink {
  return (
    typeof link === 'object' &&
    link !== null &&
    'source' in link &&
    'target' in link &&
    hasStringProp(link, 'label')
  )
}

function getEndpointId(endpoint: string | number | { id?: string | number } | undefined): string {
  if (endpoint === undefined) return ''
  return typeof endpoint === 'object' ? String(endpoint.id ?? '') : String(endpoint)
}

/** BFS로 노드 집합의 연결 컴포넌트를 계산해 nodeId → componentIndex 맵을 반환한다. */
function buildComponentMap(nodeIds: string[], edgePairs: [string, string][]): Map<string, number> {
  const adj = new Map<string, Set<string>>()
  for (const id of nodeIds) adj.set(id, new Set())
  for (const [s, t] of edgePairs) {
    if (s && t) { adj.get(s)?.add(t); adj.get(t)?.add(s) }
  }
  const visited = new Set<string>()
  const map = new Map<string, number>()
  let numComps = 0
  for (const id of nodeIds) {
    if (visited.has(id)) continue
    let head = 0
    const queue = [id]
    visited.add(id)
    while (head < queue.length) {
      const cur = queue[head++]
      map.set(cur, numComps)
      for (const nb of adj.get(cur) ?? []) {
        if (!visited.has(nb)) { visited.add(nb); queue.push(nb) }
      }
    }
    numComps++
  }
  return map
}

type SimNodeBase = { id: string; x: number; y: number; vx: number; vy: number }

/** compOf 맵을 기반으로 연결 컴포넌트 중심으로 노드를 끌어당기는 d3 force 콜백을 반환한다. */
function makeClusterForce(nodes: readonly { id: string }[], compOf: Map<string, number>, strength: number) {
  // 틱마다 Map 재할당 시 GC 압력을 피하기 위해 클로저 수준에서 선언.
  const compCenter = new Map<number, { x: number; y: number; count: number }>()
  return (alpha: number) => {
    const simNodes = nodes as unknown as SimNodeBase[]
    compCenter.clear()
    for (const n of simNodes) {
      const comp = compOf.get(n.id)
      if (comp === undefined) continue
      const c = compCenter.get(comp) ?? { x: 0, y: 0, count: 0 }
      c.x += n.x; c.y += n.y; c.count++
      compCenter.set(comp, c)
    }
    for (const c of compCenter.values()) {
      if (c.count <= 1) continue
      c.x /= c.count; c.y /= c.count
    }
    for (const n of simNodes) {
      const comp = compOf.get(n.id)
      if (comp === undefined) continue
      const c = compCenter.get(comp)
      if (!c || c.count <= 1) continue
      n.vx += (c.x - n.x) * alpha * strength
      n.vy += (c.y - n.y) * alpha * strength
    }
  }
}

// ── Side panel ────────────────────────────────────────────────────────────────

interface SidePanelProps {
  entity: OntologyEntity | null
  entityMap: Map<string, OntologyEntity>
  relationships: OntologyRelationship[]
  contextNodes: Array<{ id: string; title: string; source: string; url?: string }>
  onClose: () => void
}

function SidePanel({ entity, entityMap, relationships, contextNodes, onClose }: SidePanelProps) {
  const entityId = entity?.id ?? null
  const sourceNodeIds = entity?.source_node_ids ?? EMPTY_NODE_IDS

  const outgoing = useMemo(
    () => entityId ? relationships.filter(r => r.from === entityId) : [],
    [relationships, entityId]
  )
  const incoming = useMemo(
    () => entityId ? relationships.filter(r => r.to === entityId) : [],
    [relationships, entityId]
  )
  const sources = useMemo(
    () => sourceNodeIds.length > 0
      ? contextNodes.filter(n => sourceNodeIds.includes(n.id))
      : [],
    [contextNodes, sourceNodeIds]
  )

  if (!entity) return null
  const totalConnections = outgoing.length + incoming.length

  return (
    <div style={{
      position: 'absolute', top: 0, right: 0, width: 220,
      height: '100%', background: 'rgba(15,23,42,0.96)',
      borderLeft: '1px solid rgba(255,255,255,0.08)',
      padding: '14px 14px', overflowY: 'auto', zIndex: 10,
      backdropFilter: 'blur(8px)',
    }}>
      {/* Close */}
      <button onClick={onClose} style={{
        float: 'right', background: 'none', border: 'none',
        cursor: 'pointer', fontSize: 16, color: '#64748b',
        lineHeight: 1, padding: 0,
      }}>×</button>

      {/* Type badge */}
      <div style={{
        display: 'inline-block', padding: '2px 8px', borderRadius: 4,
        background: (NODE_COLORS[entity.type] ?? '#94a3b8') + '28',
        border: '1px solid ' + (NODE_COLORS[entity.type] ?? '#94a3b8') + '60',
        color: NODE_COLORS[entity.type] ?? '#94a3b8',
        fontSize: 10, fontWeight: 700, letterSpacing: '0.05em',
        textTransform: 'uppercase', marginBottom: 8,
      }}>
        {entity.type}
      </div>

      {/* Name */}
      <h3 style={{ margin: '0 0 4px', fontSize: 14, fontWeight: 700, color: '#f1f5f9', lineHeight: 1.3 }}>
        {entity.name}
      </h3>

      {/* Connection count */}
      {totalConnections > 0 && (
        <p style={{ margin: '0 0 14px', fontSize: 11, color: '#64748b' }}>
          {totalConnections} connection{totalConnections !== 1 ? 's' : ''}
        </p>
      )}

      {/* Outgoing relationships */}
      {outgoing.length > 0 && (
        <div style={{ marginBottom: 12 }}>
          {outgoing.map((r, i) => {
            const target = entityMap.get(r.to)
            if (!target) return null
            return (
              <div key={i} style={{
                padding: '6px 8px', borderRadius: 6, marginBottom: 4,
                background: 'rgba(255,255,255,0.04)',
                border: '1px solid rgba(255,255,255,0.06)',
              }}>
                <div style={{ fontSize: 10, color: EDGE_COLORS[r.type] ?? '#94a3b8', fontWeight: 600, marginBottom: 2 }}>
                  → {REL_LABEL[r.type] ?? r.type}
                </div>
                <div style={{ fontSize: 12, color: '#cbd5e1', fontWeight: 500 }}>
                  {target.name}
                </div>
                <div style={{ fontSize: 10, color: '#475569' }}>
                  {target.type}
                </div>
              </div>
            )
          })}
        </div>
      )}

      {/* Incoming relationships */}
      {incoming.length > 0 && (
        <div style={{ marginBottom: 12 }}>
          {incoming.map((r, i) => {
            const src = entityMap.get(r.from)
            if (!src) return null
            return (
              <div key={i} style={{
                padding: '6px 8px', borderRadius: 6, marginBottom: 4,
                background: 'rgba(255,255,255,0.04)',
                border: '1px solid rgba(255,255,255,0.06)',
              }}>
                <div style={{ fontSize: 10, color: '#64748b', fontWeight: 600, marginBottom: 2 }}>
                  ← {REL_LABEL[r.type] ?? r.type}
                </div>
                <div style={{ fontSize: 12, color: '#cbd5e1', fontWeight: 500 }}>
                  {src.name}
                </div>
                <div style={{ fontSize: 10, color: '#475569' }}>
                  {src.type}
                </div>
              </div>
            )
          })}
        </div>
      )}

      {/* No connections */}
      {totalConnections === 0 && (
        <p style={{ fontSize: 11, color: '#475569', margin: '0 0 14px' }}>No mapped relationships</p>
      )}

      {/* Sources */}
      {sources.length > 0 && (
        <>
          <div style={{ fontSize: 10, color: '#475569', fontWeight: 600, letterSpacing: '0.04em', textTransform: 'uppercase', marginBottom: 6 }}>
            Sources
          </div>
          {sources.map(s => (
            <div key={s.id} style={{ fontSize: 11, marginBottom: 4 }}>
              {s.url
                ? <a href={s.url} target="_blank" rel="noreferrer" style={{ color: '#818cf8', textDecoration: 'none' }}>{s.title}</a>
                : <span style={{ color: '#94a3b8' }}>{s.title}</span>
              }
              <span style={{ color: '#475569', marginLeft: 4 }}>({s.source})</span>
            </div>
          ))}
        </>
      )}
    </div>
  )
}

// ── Main component ────────────────────────────────────────────────────────────

interface OntologyGraphProps {
  data: OntologyData
  contextNodes?: Array<{ id: string; title: string; source: string; url?: string }>
  width?: number
  autoSelectId?: string
}

export const OntologyGraph = memo(function OntologyGraph({ data, contextNodes = [], width, autoSelectId }: OntologyGraphProps) {
  const [selectedEntity, setSelectedEntity] = useState<OntologyEntity | null>(() =>
    autoSelectId ? (data.entities.find(e => e.id === autoSelectId) ?? null) : null
  )
  const [hiddenTypes, setHiddenTypes] = useState<Set<string>>(new Set())
  const graphRef = useRef<OntologyGraphHandle | undefined>(undefined)
  const prevNodeIdsRef = useRef<Set<string>>(new Set())
  const pendingNewIdsRef = useRef<string[]>([])

  const entityMap = useMemo(
    () => new Map(data.entities.map(e => [e.id, e])),
    [data.entities]
  )

  useEffect(() => {
    setSelectedEntity(autoSelectId ? (entityMap.get(autoSelectId) ?? null) : null)
  }, [autoSelectId, entityMap])

  const handleEngineStop = useCallback(() => {
    const fg = graphRef.current
    if (!fg) return
    const newIds = pendingNewIdsRef.current
    pendingNewIdsRef.current = []
    if (newIds.length === 0) {
      fg.zoomToFit(400, 24)
      return
    }
    const newNodeSet = new Set(newIds)
    const positioned = (graphData.nodes as Array<{ id: string; x?: number; y?: number }>)
      .filter(n => newNodeSet.has(n.id) && n.x != null && n.y != null)
    if (positioned.length === 0) { fg.zoomToFit(400, 24); return }
    const cx = positioned.reduce((s, n) => s + n.x!, 0) / positioned.length
    const cy = positioned.reduce((s, n) => s + n.y!, 0) / positioned.length
    fg.centerAt(cx, cy, 400)
  }, [graphData])

  const graphNodes = useMemo<GraphNode[]>(() =>
    data.entities
      .filter(e => !hiddenTypes.has(e.type))
      .map(e => ({ ...e, color: NODE_COLORS[e.type] ?? '#94a3b8' })),
    [data.entities, hiddenTypes]
  )

  const graphData = useMemo(() => {
    const nodeIds = graphNodes.map(n => n.id)
    const visibleIds = new Set(nodeIds)
    const edgePairs: [string, string][] = []
    const links: GraphLink[] = []
    for (const r of data.relationships) {
      if (visibleIds.has(r.from) && visibleIds.has(r.to)) {
        edgePairs.push([r.from, r.to])
        links.push({ source: r.from, target: r.to, type: r.type, color: EDGE_COLORS[r.type] ?? '#cbd5e1' })
      }
    }
    return { nodes: graphNodes, links, edgePairs, nodeIds }
  }, [graphNodes, data.relationships])

  const compOf = useMemo(() => buildComponentMap(
    graphData.nodeIds,
    graphData.edgePairs
  ), [graphData])

  useEffect(() => {
    const prev = prevNodeIdsRef.current
    const newIds = graphData.nodes.filter(n => !prev.has(n.id)).map(n => n.id)
    pendingNewIdsRef.current = newIds
    prevNodeIdsRef.current = new Set(graphData.nodes.map(n => n.id))
  }, [graphData])

  useEffect(() => {
    const fg = graphRef.current
    if (!fg || graphData.nodes.length === 0) return
    let cancelled = false

    fg.d3Force('cluster', makeClusterForce(graphData.nodes, compOf, 0.08))
    fg.d3Force('charge')?.strength(-350)
    fg.d3Force('link')?.distance(100)

    import('d3-force-3d').then(({ forceCollide }) => {
      if (cancelled) return
      fg.d3Force('collide', forceCollide(42))
      fg.d3ReheatSimulation()
    })
    return () => {
      cancelled = true
      fg.d3Force('cluster', null)
      fg.d3Force('collide', null)
    }
  }, [graphData])

  // Nodes/edges connected to the selected entity
  const highlightSet = useMemo(() => {
    if (!selectedEntity) return null
    const nodes = new Set<string>([selectedEntity.id])
    const links = new Set<string>()
    data.relationships.forEach(r => {
      if (r.from === selectedEntity.id) { nodes.add(r.to); links.add(`${r.from}→${r.to}`) }
      if (r.to === selectedEntity.id)   { nodes.add(r.from); links.add(`${r.from}→${r.to}`) }
    })
    return { nodes, links }
  }, [selectedEntity, data.relationships])

  const usedTypes = useMemo(() => [...new Set(data.entities.map(e => e.type))], [data.entities])

  const toggleType = useCallback((type: string) => {
    setHiddenTypes(prev => {
      const next = new Set(prev)
      next.has(type) ? next.delete(type) : next.add(type)
      return next
    })
  }, [])

  const getNodeColor = useCallback((node: GraphNode) => {
    if (!highlightSet) return node.color
    return highlightSet.nodes.has(node.id) ? node.color : node.color + '30'
  }, [highlightSet])

  const getLinkColor = useCallback((link: GraphLink) => {
    if (!highlightSet) return link.color
    const srcId = getEndpointId(link.source)
    const tgtId = getEndpointId(link.target)
    return highlightSet.links.has(`${srcId}→${tgtId}`) ? link.color : link.color + '25'
  }, [highlightSet])

  const handleNodeClick = useCallback((node: unknown) => {
    if (!isGraphNode(node)) return
    setSelectedEntity(prev => prev?.id === node.id ? null : (entityMap.get(node.id) ?? null))
  }, [entityMap])

  return (
    <div style={{ position: 'relative', border: '1px solid #e2e8f0', borderRadius: 12, overflow: 'hidden', background: '#f8fafc' }}>
      {/* Header */}
      <div style={{ padding: '10px 14px', borderBottom: '1px solid #e2e8f0', background: '#fff' }}>
        <p style={{ margin: 0, fontSize: 12, color: '#64748b' }}>{data.domain_summary}</p>
      </div>


      {/* Legend */}
      <div style={{ padding: '7px 14px', display: 'flex', gap: 6, flexWrap: 'wrap', borderBottom: '1px solid #e2e8f0', background: '#fff' }}>
        {usedTypes.map(type => (
          <button
            key={type}
            onClick={() => toggleType(type)}
            style={{
              display: 'flex', alignItems: 'center', gap: 4,
              padding: '2px 8px', borderRadius: 4, fontSize: 11,
              border: '1.5px solid ' + (NODE_COLORS[type] ?? '#94a3b8'),
              background: hiddenTypes.has(type) ? '#fff' : (NODE_COLORS[type] ?? '#94a3b8'),
              color: hiddenTypes.has(type) ? (NODE_COLORS[type] ?? '#94a3b8') : '#fff',
              cursor: 'pointer', fontWeight: 600, transition: 'all 0.15s',
            }}
          >
            {type}
          </button>
        ))}
      </div>

      {/* Graph */}
      <div style={{ position: 'relative', height: 300 }}>
        <ForceGraph2D<GraphNode, GraphLinkData>
          ref={graphRef}
          graphData={graphData}
          width={width}
          height={300}
          warmupTicks={120}
          cooldownTicks={0}
          minZoom={0.6}
          onEngineStop={handleEngineStop}
          nodeId="id"
          nodeLabel={(node: unknown) => isGraphNode(node) ? `${node.name} · ${node.type}` : ''}
          nodeColor={(node: unknown) => isGraphNode(node) ? getNodeColor(node) : '#94a3b8'}
          nodeRelSize={9}
          linkColor={(link: unknown) => isGraphLink(link) ? getLinkColor(link) : '#cbd5e1'}
          linkWidth={2}
          linkCurvature={0.25}
          linkDirectionalArrowLength={6}
          linkDirectionalArrowRelPos={1}
          linkLineDash={(link: unknown) => isGraphLink(link) && EDGE_DASHED[link.type] ? [4, 2] : null}
          onNodeClick={handleNodeClick}
          backgroundColor="#f8fafc"
        />
        {selectedEntity && (
          <SidePanel
            entity={selectedEntity}
            entityMap={entityMap}
            relationships={data.relationships}
            contextNodes={contextNodes}
            onClose={() => setSelectedEntity(null)}
          />
        )}
      </div>
    </div>
  )
})

// ── ContextGraph ───────────────────────────────────────────────────────────────

/** weight를 [0, 1] 범위로 정규화한다. weight 범위: 8(최소) ~ 30+(최대) */
function normalizeWeight(link: ContextRenderLinkData): number {
  const w = link.weight ?? 8
  return Math.min(Math.max((w - 8) / 22, 0), 1)
}

function getSourceKey(source: string): string {
  return source.split(':')[0]
}

function getSourceColor(source: string): string {
  for (const [key, color] of Object.entries(SOURCE_COLORS)) {
    if (source.startsWith(key) || source === key) return color
  }
  return '#94a3b8'
}

interface ContextGraphProps {
  data: ContextGraphData
  width?: number
}

export const ContextGraph = memo(function ContextGraph({ data, width: widthProp }: ContextGraphProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [measuredWidth, setMeasuredWidth] = useState<number>(widthProp ?? 520)
  useEffect(() => {
    if (widthProp !== undefined) return
    const el = containerRef.current
    if (!el) return
    const ro = new ResizeObserver(entries => {
      const w = entries[0]?.contentRect.width
      if (w) setMeasuredWidth(w)
    })
    ro.observe(el)
    return () => ro.disconnect()
  }, [widthProp])
  const width = widthProp ?? measuredWidth

  const [hiddenSources, setHiddenSources] = useState<Set<string>>(new Set())
  const toggleSource = useCallback((src: string) => {
    setHiddenSources(prev => {
      const next = new Set(prev)
      next.has(src) ? next.delete(src) : next.add(src)
      return next
    })
  }, [])

  const [hoveredLink, setHoveredLink] = useState<{ key: string; label: string | null } | null>(null)

  const usedSources = useMemo(() => {
    const srcSet = new Set<string>()
    for (const n of data.nodes) srcSet.add(getSourceKey(n.source))
    return [...srcSet]
  }, [data.nodes])

  const graphNodes = useMemo(() => {
    const nodes: ContextRenderNode[] = []
    for (const n of data.nodes) {
      const src = getSourceKey(n.source)
      if (!hiddenSources.has(src)) nodes.push({ ...n, color: getSourceColor(src) })
    }
    return nodes
  }, [data.nodes, hiddenSources])

  const graphData = useMemo(() => {
    const nodeIds = graphNodes.map(n => n.id)
    const visibleIds = new Set(nodeIds)
    const edgePairs: [string, string][] = []
    const links: ContextRenderLink[] = []
    for (const e of data.edges) {
      if (visibleIds.has(e.source) && visibleIds.has(e.target)) {
        edgePairs.push([e.source, e.target])
        links.push({ ...e })
      }
    }
    return { nodes: graphNodes, links, edgePairs, nodeIds }
  }, [graphNodes, data.edges])

  const graphRef = useRef<ContextGraphHandle | undefined>(undefined)
  const prevNodeIdsRef = useRef<Set<string>>(new Set())
  const pendingNewIdsRef = useRef<string[]>([])

  const compOf = useMemo(() => buildComponentMap(
    graphData.nodeIds,
    graphData.edgePairs
  ), [graphData])

  useEffect(() => {
    const prev = prevNodeIdsRef.current
    const newIds = graphData.nodes.filter(n => !prev.has(n.id)).map(n => n.id)
    pendingNewIdsRef.current = newIds
    prevNodeIdsRef.current = new Set(graphData.nodes.map(n => n.id))
  }, [graphData])

  useEffect(() => {
    const fg = graphRef.current
    if (!fg || graphData.nodes.length === 0) return
    let cancelled = false

    fg.d3Force('charge')?.strength(-700)
    fg.d3Force('link')?.distance((link: ContextRenderLink) =>
      260 - normalizeWeight(link) * 180  // 8→260px, 30+→80px
    )
    fg.d3Force('cluster', makeClusterForce(graphData.nodes, compOf, 0.06))

    import('d3-force-3d').then(({ forceCollide }) => {
      if (cancelled) return
      fg.d3Force('collide', forceCollide(65))
      fg.d3ReheatSimulation()
    })
    return () => {
      cancelled = true
      fg.d3Force('cluster', null)
      fg.d3Force('collide', null)
    }
  }, [graphData])

  const handleEngineStop = useCallback(() => {
    const fg = graphRef.current
    if (!fg) return
    const newIds = pendingNewIdsRef.current
    pendingNewIdsRef.current = []
    if (newIds.length === 0) {
      fg.zoomToFit(400, 24)
      return
    }
    const newNodeSet = new Set(newIds)
    const positioned = (graphData.nodes as Array<{ id: string; x?: number; y?: number }>)
      .filter(n => newNodeSet.has(n.id) && n.x != null && n.y != null)
    if (positioned.length === 0) { fg.zoomToFit(400, 24); return }
    const cx = positioned.reduce((s, n) => s + n.x!, 0) / positioned.length
    const cy = positioned.reduce((s, n) => s + n.y!, 0) / positioned.length
    fg.centerAt(cx, cy, 400)
  }, [graphData])

  const handleNodeClick = useCallback((node: ContextRenderNode) => {
    if (node.url) window.open(node.url, '_blank', 'noreferrer')
  }, [])

  const getLinkColor = useCallback((link: ContextRenderLink) => {
    const key = `${getEndpointId(link.source)}→${getEndpointId(link.target)}`
    if (hoveredLink?.key === key) return '#f1f5f9'
    const t = normalizeWeight(link)
    const opacity = (0.15 + t * 0.55).toFixed(2)      // 0.15 ~ 0.70
    return `rgba(148,163,184,${opacity})`
  }, [hoveredLink])

  const getLinkWidth = useCallback((link: ContextRenderLink) => {
    const key = `${getEndpointId(link.source)}→${getEndpointId(link.target)}`
    if (hoveredLink?.key === key) return 4
    return 1.5 + normalizeWeight(link) * 2              // 1.5 ~ 3.5
  }, [hoveredLink])

  const handleLinkHover = useCallback((link: ContextRenderLink | null) => {
    if (!link) { setHoveredLink(null); return }
    const srcId = getEndpointId(link.source)
    const tgtId = getEndpointId(link.target)
    setHoveredLink({ key: `${srcId}→${tgtId}`, label: link.label })
  }, [])

  return (
    <div ref={containerRef} style={{ position: 'relative', border: '1px solid #e2e8f0', borderRadius: 12, overflow: 'hidden', background: '#f8fafc' }}>
      {/* Legend */}
      <div style={{ padding: '7px 14px', display: 'flex', gap: 6, flexWrap: 'wrap', borderBottom: '1px solid #e2e8f0', background: '#fff' }}>
        {usedSources.map(src => {
          const color = getSourceColor(src)
          const hidden = hiddenSources.has(src)
          return (
            <button
              key={src}
              onClick={() => toggleSource(src)}
              style={{
                display: 'flex', alignItems: 'center', gap: 4,
                padding: '2px 8px', borderRadius: 4, fontSize: 11,
                border: `1.5px solid ${color}`,
                background: hidden ? '#fff' : color,
                color: hidden ? color : '#fff',
                cursor: 'pointer', fontWeight: 600, transition: 'all 0.15s',
              }}
            >
              {src}
            </button>
          )
        })}
      </div>

      {/* Hover label tooltip */}
      {hoveredLink?.label && (
        <div style={{
          position: 'absolute', top: 50, left: '50%', transform: 'translateX(-50%)',
          background: 'rgba(15,23,42,0.9)', color: '#e2e8f0',
          padding: '3px 10px', borderRadius: 6, fontSize: 11, fontWeight: 500,
          pointerEvents: 'none', zIndex: 20,
          border: '1px solid rgba(255,255,255,0.1)',
          backdropFilter: 'blur(4px)',
        }}>
          {hoveredLink.label}
        </div>
      )}

      {/* Graph */}
      <ForceGraph2D<ContextRenderNode, ContextRenderLinkData>
        ref={graphRef}
        graphData={graphData}
        width={width}
        height={520}
        warmupTicks={200}
        cooldownTicks={0}
        minZoom={0.6}
        onEngineStop={handleEngineStop}
        nodeId="id"
        nodeLabel={(node: unknown) => isContextRenderNode(node) ? `${node.title}\n${node.source}` : ''}
        nodeColor={(node: unknown) => isContextRenderNode(node) ? node.color : '#94a3b8'}
        nodeRelSize={7}
        linkColor={(link: unknown) => isContextRenderLink(link) ? getLinkColor(link) : 'rgba(148,163,184,0.3)'}
        linkWidth={(link: unknown) => isContextRenderLink(link) ? getLinkWidth(link) : 1}
        linkCurvature={0.25}
        onLinkHover={(link: unknown) => handleLinkHover(isContextRenderLink(link) ? link : null)}
        onNodeClick={(node: unknown) => {
          if (isContextRenderNode(node)) handleNodeClick(node)
        }}
        backgroundColor="#f8fafc"
      />
    </div>
  )
})
