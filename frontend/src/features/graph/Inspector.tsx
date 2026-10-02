/**
 * Right-hand panel of the graph: what is selected, and — for a link — WHY IT EXISTS (plan §20).
 */
import { Link } from 'react-router'
import { ArrowRight, ChartGantt, Crosshair, ExternalLink, MousePointerClick, Waypoints } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import type { GraphEdge, GraphNode } from '@/domain/types'
import { AssertionLabel, StatusBadge } from '@/design-system/badges'
import { ConfidenceIndicator } from '@/design-system/ConfidenceIndicator'
import { EvidenceChip } from '@/features/extraction/components'
import type { Selection } from './GraphCanvas'
import { nodeTerm, relationshipTerms } from './terms'

interface Props {
  caseRef: string
  selection: Selection
  nodes: Map<string, GraphNode>
  edges: GraphEdge[]
  focus: string | null
  depth: number
  onSelect: (selection: Selection) => void
  onFocus: (id: string | null, depth?: number) => void
}

export function Inspector({ caseRef, selection, nodes, edges, focus, depth, onSelect, onFocus }: Props) {
  if (!selection) {
    return (
      <div className="flex flex-col items-center gap-2 px-4 py-10 text-center text-sm text-muted-foreground">
        <MousePointerClick aria-hidden className="size-6" />
        <p>Select an item to see its details, or a link to see <strong className="text-foreground">why it exists</strong>.</p>
      </div>
    )
  }
  if (selection.kind === 'node') {
    const node = nodes.get(selection.id)
    return node ? (
      <NodePanel caseRef={caseRef} node={node} nodes={nodes} edges={edges} focus={focus} depth={depth} onSelect={onSelect} onFocus={onFocus} />
    ) : null
  }
  const edge = edges.find((e) => e.id === selection.id)
  return edge ? <EdgePanel caseRef={caseRef} edge={edge} nodes={nodes} onSelect={onSelect} /> : null
}

function NodeName({ node }: { node: GraphNode }) {
  const term = nodeTerm(node)
  return (
    <span className="inline-flex max-w-full min-w-0 items-center gap-1.5">
      <term.icon aria-hidden className="size-3.5 shrink-0 text-muted-foreground" />
      <span className="shrink-0 font-mono text-xs">{node.reference}</span>
      <span className="truncate">{node.label}</span>
    </span>
  )
}

function NodePanel({ caseRef, node, nodes, edges, focus, depth, onSelect, onFocus }: Omit<Props, 'selection'> & { node: GraphNode }) {
  const term = nodeTerm(node)
  const links = edges.filter((e) => e.source === node.id || e.target === node.id)
  const occurredAt = node.details.occurred_at as string | null | undefined
  return (
    <div className="space-y-4 p-4">
      <div className="space-y-1">
        <p className="flex items-center gap-1.5 text-xs text-muted-foreground"><term.icon aria-hidden className="size-3.5" /> {term.label}</p>
        <h2 className="font-semibold break-words"><span className="font-mono">{node.reference}</span> · {node.label}</h2>
        <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
          {node.reviewStatus && <StatusBadge kind="review" status={node.reviewStatus} />}
          <span>{links.length} link{links.length === 1 ? '' : 's'}</span>
          {occurredAt && <span>· {new Date(occurredAt).toLocaleString()}</span>}
        </div>
      </div>

      <div className="flex flex-wrap gap-2">
        {node.kind === 'entity' && (
          <>
            <Button asChild size="sm" variant="outline"><Link to={`/investigations/${caseRef}/entities/${node.reference}`}><ExternalLink /> Profile</Link></Button>
            <Button asChild size="sm" variant="outline"><Link to={`/timeline?entity=${node.reference}`}><ChartGantt /> Timeline</Link></Button>
          </>
        )}
        {node.kind === 'evidence' && (
          <Button asChild size="sm" variant="outline"><Link to={`/investigations/${caseRef}/evidence/${node.reference}`}><ExternalLink /> Open evidence</Link></Button>
        )}
      </div>

      <div className="space-y-1.5 rounded-md border p-3">
        <p className="text-xs font-medium">Focus on this item</p>
        <p className="text-xs text-muted-foreground">Show only what is connected to it, up to a number of steps away.</p>
        <div className="flex items-center gap-2">
          <Select value={String(focus === node.id ? depth : 1)} onValueChange={(v) => onFocus(node.id, Number(v))}>
            <SelectTrigger size="sm" className="w-28" aria-label="Steps away"><SelectValue /></SelectTrigger>
            <SelectContent>
              {[1, 2, 3].map((d) => <SelectItem key={d} value={String(d)}>{d} step{d === 1 ? '' : 's'}</SelectItem>)}
            </SelectContent>
          </Select>
          {focus === node.id ? (
            <Button size="sm" variant="ghost" onClick={() => onFocus(null)}>Show whole case</Button>
          ) : (
            <Button size="sm" variant="outline" onClick={() => onFocus(node.id, 1)}><Crosshair /> Focus</Button>
          )}
        </div>
      </div>

      {links.length > 0 && (
        <div className="space-y-1.5">
          <h3 className="text-xs font-medium tracking-wide text-muted-foreground uppercase">Links</h3>
          <ul className="divide-y rounded-md border">
            {links.map((link) => {
              const other = nodes.get(link.source === node.id ? link.target : link.source)
              return (
                <li key={link.id}>
                  <button
                    type="button"
                    onClick={() => onSelect({ kind: 'edge', id: link.id })}
                    className="flex w-full flex-col items-start gap-0.5 px-3 py-2 text-left text-sm outline-none hover:bg-accent focus-visible:ring-2 focus-visible:ring-ring"
                  >
                    <span className="text-xs text-muted-foreground">{relationshipTerms[link.type].label}</span>
                    {other && <NodeName node={other} />}
                  </button>
                </li>
              )
            })}
          </ul>
        </div>
      )}
    </div>
  )
}

function EdgePanel({ caseRef, edge, nodes, onSelect }: { caseRef: string; edge: GraphEdge; nodes: Map<string, GraphNode>; onSelect: (s: Selection) => void }) {
  const source = nodes.get(edge.source)
  const target = nodes.get(edge.target)
  const term = relationshipTerms[edge.type]
  const correlation = edge.details.correlation as string | undefined
  return (
    <div className="space-y-4 p-4">
      <div className="space-y-2">
        <p className="text-xs font-semibold tracking-wide text-primary uppercase">Why this relationship exists</p>
        <div className="space-y-1 text-sm">
          {source && (
            <button type="button" className="block max-w-full text-left hover:underline" onClick={() => onSelect({ kind: 'node', id: source.id })}>
              <NodeName node={source} />
            </button>
          )}
          <p className="flex items-center gap-1 text-xs font-medium text-muted-foreground"><ArrowRight aria-hidden className="size-3.5" /> {term.label}</p>
          {target && (
            <button type="button" className="block max-w-full text-left hover:underline" onClick={() => onSelect({ kind: 'node', id: target.id })}>
              <NodeName node={target} />
            </button>
          )}
        </div>
      </div>

      <p className="rounded-md border bg-muted/40 p-3 text-sm">{edge.why}</p>

      <dl className="grid grid-cols-[7rem_minmax(0,1fr)] items-center gap-x-3 gap-y-2 text-sm">
        <dt className="text-muted-foreground">Confidence</dt>
        <dd><ConfidenceIndicator score={edge.confidence} /></dd>
        <dt className="text-muted-foreground">Review</dt>
        <dd><StatusBadge kind="review" status={edge.reviewStatus} /></dd>
        <dt className="text-muted-foreground">How we know</dt>
        <dd className="flex flex-wrap gap-1">{edge.assertionKinds.map((k) => <AssertionLabel key={k} kind={k} />)}</dd>
        <dt className="text-muted-foreground">Evidence</dt>
        <dd className="flex flex-wrap gap-1">{edge.supportingEvidence.map((ref) => <EvidenceChip key={ref} reference={ref} caseRef={caseRef} />)}</dd>
        {edge.supportingEvents.length > 0 && (
          <>
            <dt className="text-muted-foreground">Events</dt>
            <dd className="font-mono text-xs">{edge.supportingEvents.join(', ')}</dd>
          </>
        )}
      </dl>

      <p className="text-xs text-muted-foreground">{term.description}</p>

      {correlation && (
        <Button asChild size="sm" variant="outline">
          <Link to={`/investigations/${caseRef}/correlations/${correlation}`}><Waypoints /> Full explanation and review ({correlation})</Link>
        </Button>
      )}
    </div>
  )
}
