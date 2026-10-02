/**
 * GraphService (plan §20): the relationship graph of one investigation, built on the server.
 */
import type { GraphDto } from '@/api/types'
import type { AssertionKind, GraphEdgeType, GraphNodeKind, RelationshipGraph, ReviewStatus } from '@/domain/types'
import { apiGet } from './apiClient'

export interface GraphQuery {
  include_events?: boolean
  include_evidence?: boolean
  include_rejected?: boolean
  include_stale?: boolean
  entity_type?: string[]
  min_level?: 'low' | 'medium' | 'high'
  focus?: string
  depth?: number
}

function queryString(query: GraphQuery): string {
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(query)) {
    if (value === undefined || value === '') continue
    if (Array.isArray(value)) value.forEach((v) => params.append(key, String(v)))
    else params.set(key, String(value))
  }
  const text = params.toString()
  return text ? `?${text}` : ''
}

const toGraph = (dto: GraphDto): RelationshipGraph => ({
  nodes: dto.nodes.map((n) => ({
    id: n.id,
    kind: n.kind as GraphNodeKind,
    type: n.type,
    reference: n.reference,
    label: n.label,
    reviewStatus: (n.review_status ?? null) as ReviewStatus | null,
    degree: n.degree,
    details: n.details as Record<string, unknown>,
  })),
  edges: dto.edges.map((e) => ({
    id: e.id,
    source: e.source,
    target: e.target,
    type: e.type as GraphEdgeType,
    why: e.why,
    confidence: e.confidence,
    reviewStatus: e.review_status as ReviewStatus,
    assertionKinds: e.assertion_kinds as AssertionKind[],
    supportingEvidence: e.supporting_evidence,
    supportingEvents: e.supporting_events,
    details: e.details as Record<string, unknown>,
  })),
  totalNodes: dto.total_nodes,
  totalEdges: dto.total_edges,
  truncated: dto.truncated,
})

export const GraphService = {
  async get(caseRef: string, query: GraphQuery = {}): Promise<RelationshipGraph> {
    return toGraph(await apiGet<GraphDto>(`/investigations/${encodeURIComponent(caseRef)}/graph${queryString(query)}`))
  },
}
