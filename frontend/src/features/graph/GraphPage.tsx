import { useMemo, useRef, useState } from 'react'
import { Link } from 'react-router'
import { Crosshair, Filter, FolderSearch, Maximize, Minus, Network, Plus, RefreshCw, Search, SearchX, TriangleAlert, X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Checkbox } from '@/components/ui/checkbox'
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import type { EntityType, GraphNode } from '@/domain/types'
import { ApiError } from '@/services/apiClient'
import { useGraph } from '@/services/queries'
import { StatusBadge } from '@/design-system/badges'
import { ConfidenceIndicator } from '@/design-system/ConfidenceIndicator'
import { IdTag } from '@/design-system/IdTag'
import { PageHeader } from '@/design-system/PageHeader'
import { EmptyState, ErrorState } from '@/design-system/states'
import { entityTypeTerms } from '@/design-system/vocabulary'
import { useCurrentCase } from '@/features/extraction/useCaseAccess'
import { GraphCanvas, type GraphCanvasHandle, type Selection } from './GraphCanvas'
import { Inspector } from './Inspector'
import { entityColorToken, nodeTerm, relationshipTerms } from './terms'

type Strength = 'low' | 'medium' | 'high'

/** Relationship graph (plan §20): entities, evidence and events, and why each link exists. */
export function GraphPage() {
  const caseRef = useCurrentCase()
  const canvas = useRef<GraphCanvasHandle>(null)
  // On a phone a whole-case graph is too small to read: start with the list there.
  const [view, setView] = useState<'graph' | 'list'>(() => (window.matchMedia('(max-width: 639px)').matches ? 'list' : 'graph'))
  const [showEvidence, setShowEvidence] = useState(true)
  const [showEvents, setShowEvents] = useState(false)
  const [showRejected, setShowRejected] = useState(false)
  const [entityTypes, setEntityTypes] = useState<EntityType[]>([])
  const [strength, setStrength] = useState<Strength>('low')
  const [focus, setFocus] = useState<string | null>(null)
  const [depth, setDepth] = useState(1)
  const [search, setSearch] = useState('')
  const [selection, setSelection] = useState<Selection>(null)

  const { data, isPending, isError, error, refetch, isFetching } = useGraph(caseRef, {
    include_evidence: showEvidence,
    include_events: showEvents,
    include_rejected: showRejected,
    entity_type: entityTypes.length ? entityTypes : undefined,
    min_level: strength,
    focus: focus ?? undefined,
    depth: focus ? depth : undefined,
  })
  const nodes = useMemo(() => data?.nodes ?? [], [data])
  const edges = useMemo(() => data?.edges ?? [], [data])
  const byId = useMemo(() => new Map(nodes.map((n) => [n.id, n])), [nodes])
  const matches = useMemo(() => findMatches(nodes, search), [nodes, search])
  // A selection that a new filter removed is simply no selection.
  const current: Selection =
    selection && (selection.kind === 'node' ? byId.has(selection.id) : edges.some((e) => e.id === selection.id)) ? selection : null

  if (!caseRef) {
    return (
      <div className="mx-auto max-w-3xl pt-6">
        <EmptyState icon={FolderSearch} title="No investigation selected" description="Choose an investigation in the top bar."
          action={<Button asChild variant="outline"><Link to="/investigations">Open investigations</Link></Button>} />
      </div>
    )
  }

  const select = (next: Selection) => {
    setSelection(next)
    if (next?.kind === 'node') canvas.current?.center(next.id)
  }
  const goToFirstMatch = () => {
    const first = matches && [...matches][0]
    if (first) select({ kind: 'node', id: first })
  }
  const changeFocus = (id: string | null, steps = 1) => {
    setFocus(id)
    setDepth(steps)
  }
  const focusNode = focus ? byId.get(focus) : undefined

  return (
    <div className="mx-auto max-w-7xl space-y-4">
      <PageHeader
        eyebrow={<IdTag>{caseRef}</IdTag>}
        title="Relationship Graph"
        description="How people, phones, vehicles, accounts and evidence connect. Select any link to see why it exists and the evidence behind it."
        actions={
          <Tabs value={view} onValueChange={(v) => setView(v as 'graph' | 'list')}>
            <TabsList>
              <TabsTrigger value="graph">Graph</TabsTrigger>
              <TabsTrigger value="list">List</TabsTrigger>
            </TabsList>
          </Tabs>
        }
      />

      <div className="flex flex-wrap items-center gap-2">
        <form className="relative w-full sm:w-auto" onSubmit={(e) => { e.preventDefault(); goToFirstMatch() }} role="search">
          <Search aria-hidden className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Find V001, a phone, a name…" aria-label="Find in graph" className="w-full pl-8 sm:w-60" />
        </form>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="outline"><Filter /> {entityTypes.length ? `${entityTypes.length} entity type${entityTypes.length === 1 ? '' : 's'}` : 'All entity types'}</Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="start">
            <DropdownMenuLabel>Show entity types</DropdownMenuLabel>
            <DropdownMenuSeparator />
            {(Object.keys(entityTypeTerms) as EntityType[]).map((type) => (
              <DropdownMenuCheckboxItem
                key={type}
                checked={entityTypes.includes(type)}
                onSelect={(e) => e.preventDefault()}
                onCheckedChange={(on) => setEntityTypes((prev) => (on ? [...prev, type] : prev.filter((t) => t !== type)))}
              >
                {entityTypeTerms[type].plural}
              </DropdownMenuCheckboxItem>
            ))}
            {entityTypes.length > 0 && (
              <>
                <DropdownMenuSeparator />
                <DropdownMenuCheckboxItem checked={false} onCheckedChange={() => setEntityTypes([])}>Show all</DropdownMenuCheckboxItem>
              </>
            )}
          </DropdownMenuContent>
        </DropdownMenu>
        <Select value={strength} onValueChange={(v) => setStrength(v as Strength)}>
          <SelectTrigger className="w-full sm:w-52" aria-label="Correlation strength"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="low">All correlations</SelectItem>
            <SelectItem value="medium">Medium and high correlations</SelectItem>
            <SelectItem value="high">High correlations only</SelectItem>
          </SelectContent>
        </Select>
        <Toggle id="g-evidence" label="Evidence" checked={showEvidence} onChange={setShowEvidence} />
        <Toggle id="g-events" label="Events" checked={showEvents} onChange={setShowEvents} />
        <Toggle id="g-rejected" label="Rejected" checked={showRejected} onChange={setShowRejected} />
      </div>

      {(focus || data?.truncated) && (
        <div className="flex flex-wrap items-center gap-2 text-sm">
          {focus && (
            <span className="inline-flex items-center gap-2 rounded-md border bg-accent px-2 py-1">
              <Crosshair aria-hidden className="size-4 text-primary" />
              <span>Focused on <strong className="font-mono">{focusNode?.reference ?? focus.split(':')[1]}</strong>, {depth} step{depth === 1 ? '' : 's'}</span>
              <Button size="icon-xs" variant="ghost" aria-label="Show whole case" onClick={() => changeFocus(null)}><X /></Button>
            </span>
          )}
          {data?.truncated && (
            <span className="inline-flex items-center gap-1.5 text-warning">
              <TriangleAlert aria-hidden className="size-4" />
              Showing the {data.nodes.length} best-connected of {data.totalNodes} items. Focus on one item or filter to see the rest.
            </span>
          )}
        </div>
      )}

      {isError ? (
        <ErrorState description={error instanceof ApiError ? error.message : 'The graph could not be loaded.'} onRetry={() => refetch()} retrying={isFetching} />
      ) : isPending ? (
        <Skeleton className="h-[560px] w-full" />
      ) : nodes.length === 0 ? (
        <EmptyState icon={focus || entityTypes.length ? SearchX : Network} title="Nothing to show"
          description={focus || entityTypes.length ? 'No items match these filters.' : 'The graph fills up as evidence is processed and entities are found.'} />
      ) : (
        <div className="grid grid-cols-[minmax(0,1fr)] gap-4 lg:grid-cols-[minmax(0,1fr)_20rem]">
          {view === 'graph' ? (
            <Card className="relative gap-0 overflow-hidden p-0">
              <div className="h-[min(70vh,640px)] min-h-[420px]">
                <GraphCanvas ref={canvas} nodes={nodes} edges={edges} selection={current} matches={matches} onSelect={setSelection} />
              </div>
              <div className="absolute top-2 right-2 flex flex-col gap-1 rounded-lg border bg-card/90 p-1 shadow-sm backdrop-blur">
                <Button size="icon-sm" variant="ghost" aria-label="Zoom in" title="Zoom in" onClick={() => canvas.current?.zoomBy(1.25)}><Plus /></Button>
                <Button size="icon-sm" variant="ghost" aria-label="Zoom out" title="Zoom out" onClick={() => canvas.current?.zoomBy(0.8)}><Minus /></Button>
                <Button size="icon-sm" variant="ghost" aria-label="Fit all" title="Fit all" onClick={() => canvas.current?.fit()}><Maximize /></Button>
                <Button size="icon-sm" variant="ghost" aria-label="Arrange again" title="Arrange again" onClick={() => canvas.current?.relayout()}><RefreshCw /></Button>
              </div>
              <Legend />
            </Card>
          ) : (
            <ListView nodes={byId} edges={edges} selectedId={current?.kind === 'edge' ? current.id : null} onSelect={setSelection} />
          )}
          <Card className="gap-0 self-start p-0 lg:sticky lg:top-20 lg:max-h-[calc(100vh-6rem)] lg:overflow-y-auto">
            <Inspector caseRef={caseRef} selection={current} nodes={byId} edges={edges} focus={focus} depth={depth} onSelect={select} onFocus={changeFocus} />
          </Card>
        </div>
      )}
      {data && (
        <p className="text-xs text-muted-foreground">
          {data.nodes.length} items · {data.edges.length} links. Links come from extracted mentions, shared events and correlations; nothing is inferred by AI.
        </p>
      )}
    </div>
  )
}

function Toggle({ id, label, checked, onChange }: { id: string; label: string; checked: boolean; onChange: (on: boolean) => void }) {
  return (
    <div className="flex items-center gap-1.5 px-1">
      <Checkbox id={id} checked={checked} onCheckedChange={(v) => onChange(v === true)} />
      <Label htmlFor={id} className="font-normal">{label}</Label>
    </div>
  )
}

function findMatches(nodes: GraphNode[], search: string): Set<string> | null {
  const q = search.trim().toLowerCase()
  if (!q) return null
  const digits = q.replace(/\D/g, '')
  return new Set(
    nodes
      .filter((n) => n.reference.toLowerCase().includes(q) || n.label.toLowerCase().includes(q) || (digits.length >= 4 && n.label.replace(/\D/g, '').includes(digits)))
      .map((n) => n.id),
  )
}

function Legend() {
  const used: EntityType[] = ['person', 'phone_number', 'device', 'vehicle', 'account', 'organization']
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5 border-t px-3 py-2 text-xs text-muted-foreground">
      {used.map((type) => (
        <span key={type} className="inline-flex items-center gap-1.5">
          <span aria-hidden className="size-2.5 rounded-full" style={{ background: `var(${entityColorToken[type]})` }} />
          {entityTypeTerms[type].label}
        </span>
      ))}
      <span className="inline-flex items-center gap-1.5"><span aria-hidden className="h-2.5 w-3.5 rounded-sm border-2 border-primary" /> Evidence</span>
      <span className="inline-flex items-center gap-1.5"><span aria-hidden className="size-2 rotate-45 bg-muted-foreground" /> Event</span>
      <span className="inline-flex items-center gap-1.5"><span aria-hidden className="w-5 border-t-2 border-dashed border-signal" /> Potential (not yet reviewed)</span>
      <span className="inline-flex items-center gap-1.5"><span aria-hidden className="w-5 border-t-2 border-success" /> Confirmed</span>
      <span className="inline-flex items-center gap-1.5"><span aria-hidden className="size-2.5 rounded-full border-2 border-success" /> Reviewed and confirmed</span>
    </div>
  )
}

/** The same graph as a table: readable by screen readers, sortable by eye, printable. */
function ListView({ nodes, edges, selectedId, onSelect }: { nodes: Map<string, GraphNode>; edges: import('@/domain/types').GraphEdge[]; selectedId: string | null; onSelect: (s: Selection) => void }) {
  const name = (id: string) => {
    const node = nodes.get(id)
    if (!node) return id
    const term = nodeTerm(node)
    return (
      <span className="flex max-w-48 min-w-0 items-center gap-1.5" title={node.label}>
        <term.icon aria-hidden className="size-3.5 shrink-0 text-muted-foreground" />
        <span className="shrink-0 font-mono text-xs">{node.reference}</span>
        <span className="truncate">{node.label}</span>
      </span>
    )
  }
  return (
    <Card className="gap-0 overflow-hidden p-0">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>From</TableHead>
            <TableHead>Relationship</TableHead>
            <TableHead>To</TableHead>
            <TableHead>Confidence</TableHead>
            <TableHead>Review</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {edges.map((edge) => (
            <TableRow key={edge.id} data-state={edge.id === selectedId ? 'selected' : undefined}>
              <TableCell>{name(edge.source)}</TableCell>
              <TableCell>
                <button type="button" className="text-left font-medium text-primary underline-offset-4 hover:underline focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none" onClick={() => onSelect({ kind: 'edge', id: edge.id })}>
                  {relationshipTerms[edge.type].label}
                </button>
              </TableCell>
              <TableCell>{name(edge.target)}</TableCell>
              <TableCell><ConfidenceIndicator score={edge.confidence} /></TableCell>
              <TableCell><StatusBadge kind="review" status={edge.reviewStatus} /></TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </Card>
  )
}
