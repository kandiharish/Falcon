import { lazy, Suspense, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router'
import { ChartGantt, FileStack, FolderSearch, Map as MapIcon, Play } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Checkbox } from '@/components/ui/checkbox'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from '@/components/ui/sheet'
import { Skeleton } from '@/components/ui/skeleton'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import type { EventType, InvestigationEvent } from '@/domain/types'
import { ApiError } from '@/services/apiClient'
import { useEntities, useEvents } from '@/services/queries'
import { IdTag } from '@/design-system/IdTag'
import { PageHeader } from '@/design-system/PageHeader'
import { EmptyState, ErrorState } from '@/design-system/states'
import { entityTypeTerms, eventTypeTerms, evidenceTypeTerms } from '@/design-system/vocabulary'
import { zoneLabel } from '@/lib/time'
import { EventRow } from '@/features/extraction/components'
import { useCaseAccess, useCaseTimeZone, useCurrentCase } from '@/features/extraction/useCaseAccess'
import { CATEGORY_OF, CATEGORY_STYLE, type Category } from './categories'
import { TimelineChart, type Lane } from './TimelineChart'

// The map pulls in Leaflet (~150 kB); load it only when someone opens the Map view.
const EventMap = lazy(() => import('./EventMap').then((m) => ({ default: m.EventMap })))
const ReplayView = lazy(() => import('./ReplayView').then((m) => ({ default: m.ReplayView })))

const ALL = 'all'
type GroupBy = 'source' | 'category' | 'entity'
type View = 'timeline' | 'map' | 'replay'

/**
 * Timeline & map (plan §17, §54): TIME → EVENT → ENTITY → LOCATION → EVIDENCE.
 * Both views share the same filters; clicking any event opens it, with its supporting evidence.
 */
export function TimelinePage() {
  const caseRef = useCurrentCase()
  const timeZone = useCaseTimeZone(caseRef)
  const { canReview } = useCaseAccess(caseRef)
  // ?view=replay (from the case page) opens the replay directly.
  const [searchParams] = useSearchParams()
  const [view, setView] = useState<View>(() => (searchParams.get('view') as View | null) ?? 'timeline')
  const [groupBy, setGroupBy] = useState<GroupBy>('source')
  const [category, setCategory] = useState<Category | typeof ALL>(ALL)
  // ?entity=V001 (from the graph or an entity profile) opens the timeline filtered to it.
  const [entity, setEntity] = useState<string>(() => searchParams.get('entity') ?? ALL)
  const [evidenceType, setEvidenceType] = useState<string>(ALL)
  const [showRejected, setShowRejected] = useState(false)
  const [selected, setSelected] = useState<InvestigationEvent | null>(null)

  const eventTypes = category === ALL ? undefined : (Object.keys(CATEGORY_OF) as EventType[]).filter((t) => CATEGORY_OF[t] === category)
  const { data: entityPage } = useEntities(caseRef)
  const { data, isPending, isError, error, refetch, isFetching } = useEvents(caseRef, {
    event_type: eventTypes,
    entity: entity === ALL ? undefined : entity,
    evidence_type: evidenceType === ALL ? undefined : evidenceType,
  })
  const events = useMemo(
    () => (data?.items ?? []).filter((e) => showRejected || e.reviewStatus !== 'rejected'),
    [data, showRejected],
  )
  const { lanes, laneIdsOf } = useMemo(() => buildLanes(events, groupBy), [events, groupBy])

  if (!caseRef) {
    return (
      <div className="mx-auto max-w-3xl pt-6">
        <EmptyState icon={FolderSearch} title="No investigation selected" description="Choose an investigation in the top bar."
          action={<Button asChild variant="outline"><Link to="/investigations">Open investigations</Link></Button>} />
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-7xl space-y-5">
      <PageHeader
        eyebrow={<IdTag>{caseRef}</IdTag>}
        title="Timeline"
        description={`What happened, when and where — every point links to its evidence. Times in ${zoneLabel(timeZone)}.`}
        actions={
          <Tabs value={view} onValueChange={(v) => setView(v as View)}>
            <TabsList>
              <TabsTrigger value="timeline"><ChartGantt /> Timeline</TabsTrigger>
              <TabsTrigger value="map"><MapIcon /> Map</TabsTrigger>
              <TabsTrigger value="replay"><Play /> Replay</TabsTrigger>
            </TabsList>
          </Tabs>
        }
      />

      <div className="flex flex-wrap items-center gap-2">
        <Select value={category} onValueChange={(v) => setCategory(v as Category | typeof ALL)}>
          <SelectTrigger className="w-52" aria-label="Filter by kind of event"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>All kinds of event</SelectItem>
            {Object.entries(CATEGORY_STYLE).map(([value, style]) => (
              <SelectItem key={value} value={value}>
                <span aria-hidden className="size-2.5 rounded-full" style={{ background: style.color }} /> {style.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select value={entity} onValueChange={setEntity}>
          <SelectTrigger className="w-60" aria-label="Filter by entity"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>Any entity</SelectItem>
            {entityPage?.items.map((e) => (
              <SelectItem key={e.reference} value={e.reference}>{e.reference} · {e.label}</SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select value={evidenceType} onValueChange={setEvidenceType}>
          <SelectTrigger className="w-52" aria-label="Filter by evidence source"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>Any evidence source</SelectItem>
            {Object.entries(evidenceTypeTerms).map(([value, term]) => (
              <SelectItem key={value} value={value}>{term.label}</SelectItem>
            ))}
          </SelectContent>
        </Select>
        {view === 'timeline' && (
          <Select value={groupBy} onValueChange={(v) => setGroupBy(v as GroupBy)}>
            <SelectTrigger className="w-48" aria-label="Group lanes by"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="source">Lanes: evidence source</SelectItem>
              <SelectItem value="category">Lanes: kind of event</SelectItem>
              <SelectItem value="entity">Lanes: entity</SelectItem>
            </SelectContent>
          </Select>
        )}
        <div className="flex items-center gap-2 pl-1">
          <Checkbox id="show-rejected" checked={showRejected} onCheckedChange={(v) => setShowRejected(v === true)} />
          <Label htmlFor="show-rejected" className="font-normal">Show rejected</Label>
        </div>
      </div>

      <Legend />

      {isError ? (
        <ErrorState description={error instanceof ApiError ? error.message : 'Events could not be loaded.'} onRetry={() => refetch()} retrying={isFetching} />
      ) : isPending ? (
        <Skeleton className="h-96 w-full" />
      ) : data.total === 0 ? (
        <EmptyState icon={FileStack} title="Nothing to show yet" description="Events appear here once evidence has been processed, or analysts record observations." />
      ) : view === 'timeline' ? (
        <TimelineChart
          events={events}
          lanes={lanes}
          laneIdsOf={laneIdsOf}
          timeZone={timeZone}
          selected={selected?.reference ?? null}
          onSelect={setSelected}
        />
      ) : view === 'replay' ? (
        <Suspense fallback={<Skeleton className="h-[60svh] w-full" />}>
          <ReplayView caseRef={caseRef} events={events} timeZone={timeZone} onSelect={setSelected} />
        </Suspense>
      ) : (
        <Suspense fallback={<Skeleton className="h-[60svh] w-full" />}>
          <EventMap events={events} timeZone={timeZone} pathEntity={entity === ALL ? null : entity} onSelect={setSelected} />
          {entity === ALL && (
            <p className="text-xs text-muted-foreground">Tip: choose an entity above to draw its movement on the map.</p>
          )}
        </Suspense>
      )}

      <Sheet open={selected !== null} onOpenChange={(open) => !open && setSelected(null)}>
        <SheetContent
          className="w-full overflow-y-auto sm:max-w-lg"
          // Focus the drawer itself (not its first label, whose tooltip would pop up uninvited).
          onOpenAutoFocus={(e) => {
            e.preventDefault()
            ;(e.currentTarget as HTMLElement).focus()
          }}
        >
          {selected && (
            <>
              <SheetHeader>
                <SheetTitle>{selected.reference} · {eventTypeTerms[selected.eventType].label}</SheetTitle>
                <SheetDescription>Supported by {selected.evidenceReference}. Open it to see the original.</SheetDescription>
              </SheetHeader>
              <Card className="mx-4 py-0">
                <CardContent>
                  <ol>
                    <EventRow
                      event={(data?.items ?? []).find((e) => e.reference === selected.reference) ?? selected}
                      caseRef={caseRef}
                      canReview={canReview}
                      compact
                    />
                  </ol>
                </CardContent>
              </Card>
              <div className="flex flex-wrap gap-2 px-4 pb-4">
                <Button asChild>
                  <Link to={`/investigations/${caseRef}/evidence/${selected.evidenceReference}`}>Open evidence {selected.evidenceReference}</Link>
                </Button>
                {selected.participants.map((p) => (
                  <Button asChild key={p.reference} variant="outline">
                    <Link to={`/investigations/${caseRef}/entities/${p.reference}`}>{p.reference} profile</Link>
                  </Button>
                ))}
              </div>
            </>
          )}
        </SheetContent>
      </Sheet>
    </div>
  )
}

function Legend() {
  return (
    <ul className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground" aria-label="Colour legend">
      {Object.values(CATEGORY_STYLE).map((style) => (
        <li key={style.label} className="flex items-center gap-1.5">
          <span aria-hidden className="size-2.5 rounded-full" style={{ background: style.color }} /> {style.label}
        </li>
      ))}
      <li className="flex items-center gap-1.5">
        <span aria-hidden className="size-2.5 rounded-full border-2 border-foreground" /> hollow = added by an analyst
      </li>
    </ul>
  )
}

function buildLanes(events: InvestigationEvent[], groupBy: GroupBy): { lanes: Lane[]; laneIdsOf: (e: InvestigationEvent) => string[] } {
  if (groupBy === 'source') {
    const ids = [...new Set(events.map((e) => e.evidenceReference))].sort()
    return {
      lanes: ids.map((id) => {
        const sample = events.find((e) => e.evidenceReference === id)!
        const type = evidenceTypeTerms[sample.evidenceType as keyof typeof evidenceTypeTerms]
        return { id, label: `${id} · ${type?.label ?? sample.evidenceType}` }
      }),
      laneIdsOf: (e) => [e.evidenceReference],
    }
  }
  if (groupBy === 'category') {
    const used = new Set(events.map((e) => CATEGORY_OF[e.eventType]))
    return {
      lanes: (Object.keys(CATEGORY_STYLE) as Category[]).filter((c) => used.has(c)).map((c) => ({ id: c, label: CATEGORY_STYLE[c].label })),
      laneIdsOf: (e) => [CATEGORY_OF[e.eventType]],
    }
  }
  // By entity: an event with two participants appears in both lanes.
  const entities = new Map<string, string>()
  for (const e of events) for (const p of e.participants) entities.set(p.reference, `${p.reference} · ${p.label} (${entityTypeTerms[p.entityType].label})`)
  const lanes = [...entities.entries()].sort(([a], [b]) => a.localeCompare(b)).map(([id, label]) => ({ id, label }))
  if (events.some((e) => e.participants.length === 0)) lanes.push({ id: '__none', label: 'No entity linked' })
  return {
    lanes,
    laneIdsOf: (e) => (e.participants.length ? [...new Set(e.participants.map((p) => p.reference))] : ['__none']),
  }
}
