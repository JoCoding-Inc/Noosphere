// frontend/src/components/OntologyGraph.tsx
import { useState, useCallback, useMemo, memo } from 'react'
import ForceGraph2D from 'react-force-graph-2d'
import type { OntologyEntity, OntologyData } from '../types'

// ── Color mappings ────────────────────────────────────────────────────────────
const NODE_COLORS: Record<string, string> = {
  framework:      '#3b82f6', // blue
  product:        '#22c55e', // green
  company:        '#f97316', // orange
  technology:     '#a855f7', // purple
  market_segment: '#eab308', // yellow
  pain_point:     '#ef4444', // red
  research:       '#14b8a6', // teal
  standard:       '#94a3b8', // gray
  concept:        '#c084fc', // lavender
  regulation:     '#92400e', // brown
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

interface GraphNode {
  id: string
  name: string
  type: string
  source_node_ids: string[]
  color: string
}

interface GraphLink {
  source: string
  target: string
  type: string
  color: string
}

interface SidePanelProps {
  entity: OntologyEntity | null
  contextNodes: Array<{ id: string; title: string; source: string; url?: string }>
  onClose: () => void
}

function SidePanel({ entity, contextNodes, onClose }: SidePanelProps) {
  if (!entity) return null
  const sources = contextNodes.filter(n => entity.source_node_ids.includes(n.id))
  return (
    <div style={{
      position: 'absolute', top: 0, right: 0, width: 240,
      height: '100%', background: '#fff', borderLeft: '1px solid #e2e8f0',
      padding: '16px', overflowY: 'auto', zIndex: 10,
    }}>
      <button onClick={onClose} style={{
        float: 'right', background: 'none', border: 'none',
        cursor: 'pointer', fontSize: 18, color: '#94a3b8',
      }}>×</button>
      <div style={{
        display: 'inline-block', padding: '2px 8px', borderRadius: 4,
        background: NODE_COLORS[entity.type] ?? '#94a3b8',
        color: '#fff', fontSize: 11, fontWeight: 600, marginBottom: 8,
      }}>
        {entity.type}
      </div>
      <h3 style={{ margin: '0 0 12px', fontSize: 15, fontWeight: 700 }}>{entity.name}</h3>
      {sources.length > 0 && (
        <>
          <p style={{ fontSize: 12, color: '#64748b', margin: '0 0 6px' }}>Sources:</p>
          {sources.map(s => (
            <div key={s.id} style={{ fontSize: 12, marginBottom: 4 }}>
              {s.url
                ? <a href={s.url} target="_blank" rel="noreferrer" style={{ color: '#6366f1' }}>{s.title}</a>
                : <span style={{ color: '#475569' }}>{s.title}</span>
              }
              <span style={{ color: '#94a3b8', marginLeft: 4 }}>({s.source})</span>
            </div>
          ))}
        </>
      )}
    </div>
  )
}

interface OntologyGraphProps {
  data: OntologyData
  contextNodes?: Array<{ id: string; title: string; source: string; url?: string }>
}

export const OntologyGraph = memo(function OntologyGraph({ data, contextNodes = [] }: OntologyGraphProps) {
  const [selectedEntity, setSelectedEntity] = useState<OntologyEntity | null>(null)
  const [hiddenTypes, setHiddenTypes] = useState<Set<string>>(new Set())

  const graphNodes = useMemo<GraphNode[]>(() =>
    data.entities
      .filter(e => !hiddenTypes.has(e.type))
      .map(e => ({ ...e, color: NODE_COLORS[e.type] ?? '#94a3b8' })),
    [data.entities, hiddenTypes]
  )

  const graphData = useMemo(() => {
    const visibleIds = new Set(graphNodes.map(n => n.id))
    const links: GraphLink[] = data.relationships
      .filter(r => visibleIds.has(r.from) && visibleIds.has(r.to))
      .map(r => ({
        source: r.from,
        target: r.to,
        type: r.type,
        color: EDGE_COLORS[r.type] ?? '#cbd5e1',
      }))
    return { nodes: graphNodes, links }
  }, [graphNodes, data.relationships])

  const usedTypes = useMemo(() => [...new Set(data.entities.map(e => e.type))], [data.entities])

  const toggleType = useCallback((type: string) => {
    setHiddenTypes(prev => {
      const next = new Set(prev)
      next.has(type) ? next.delete(type) : next.add(type)
      return next
    })
  }, [])

  return (
    <div style={{ position: 'relative', border: '1px solid #e2e8f0', borderRadius: 12, overflow: 'hidden', background: '#f8fafc' }}>
      {/* Header */}
      <div style={{ padding: '12px 16px', borderBottom: '1px solid #e2e8f0', background: '#fff' }}>
        <p style={{ margin: 0, fontSize: 12, color: '#64748b' }}>{data.domain_summary}</p>
      </div>

      {/* Legend */}
      <div style={{ padding: '8px 16px', display: 'flex', gap: 8, flexWrap: 'wrap', borderBottom: '1px solid #e2e8f0', background: '#fff' }}>
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
      <div style={{ position: 'relative', height: 400 }}>
        <ForceGraph2D
          graphData={graphData}
          nodeId="id"
          nodeLabel="name"
          nodeColor="color"
          nodeRelSize={6}
          linkColor="color"
          linkDirectionalArrowLength={6}
          linkDirectionalArrowRelPos={1}
          // @ts-expect-error linkLineDash not in typings but supported at runtime
          linkLineDash={(link: GraphLink) => EDGE_DASHED[link.type] ? [4, 2] : undefined}
          onNodeClick={(node: unknown) => {
            const n = node as GraphNode
            const entity = data.entities.find(e => e.id === n.id)
            setSelectedEntity(entity ?? null)
          }}
          backgroundColor="#f8fafc"
        />
        <SidePanel
          entity={selectedEntity}
          contextNodes={contextNodes}
          onClose={() => setSelectedEntity(null)}
        />
      </div>
    </div>
  )
})
