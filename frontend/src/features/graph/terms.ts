/** Words and colours for the relationship graph. Shape + label always back up colour (plan §36). */
import type { EntityType, EventType, EvidenceType, GraphEdgeType, GraphNode } from '@/domain/types'
import { entityTypeTerms, eventTypeTerms, evidenceTypeTerms } from '@/design-system/vocabulary'

export const relationshipTerms: Record<GraphEdgeType, { label: string; description: string }> = {
  appears_in: { label: 'Appears in', description: 'The entity was found in this evidence.' },
  communicated_with: { label: 'Communicated with', description: 'A call or message between them.' },
  connected_to: { label: 'Connected to', description: 'They took part in the same event, such as a payment.' },
  related_evidence: { label: 'Related evidence', description: 'A potential relationship found by the correlation engine.' },
  involved_in: { label: 'Involved in', description: 'The entity took part in this event.' },
  recorded_in: { label: 'Recorded in', description: 'The event was found in this evidence.' },
}

/** CSS colour tokens per entity type; resolved to real colours for the canvas at runtime. */
export const entityColorToken: Record<EntityType, string> = {
  person: '--chart-1',
  phone_number: '--chart-2',
  device: '--chart-3',
  vehicle: '--chart-4',
  account: '--chart-5',
  location: '--info',
  organization: '--inferred',
  digital_artifact: '--signal',
}

export function nodeTerm(node: GraphNode) {
  if (node.kind === 'entity') return entityTypeTerms[node.type as EntityType] ?? entityTypeTerms.digital_artifact
  if (node.kind === 'evidence') {
    const term = evidenceTypeTerms[node.type as EvidenceType] ?? evidenceTypeTerms.other
    return { label: `Evidence · ${term.label}`, icon: term.icon }
  }
  const term = eventTypeTerms[node.type as EventType] ?? eventTypeTerms.other
  return { label: `Event · ${term.label}`, icon: term.icon }
}
