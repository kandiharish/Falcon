import { useState } from 'react'
import { Link } from 'react-router'
import { Activity, FolderSearch, SearchX } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import type { EventType, InvestigationEvent, ReviewStatus } from '@/domain/types'
import { ApiError } from '@/services/apiClient'
import { useEntities, useEvents } from '@/services/queries'
import { IdTag } from '@/design-system/IdTag'
import { PageHeader } from '@/design-system/PageHeader'
import { EmptyState, ErrorState } from '@/design-system/states'
import { eventTypeTerms, reviewStatusTerms } from '@/design-system/vocabulary'
import { EventRow } from './components'
import { dayInZone, zoneLabel } from '@/lib/time'
import { useCaseAccess, useCaseTimeZone, useCurrentCase } from './useCaseAccess'

const ALL = 'all'

/** Events in time order (plan §16). The zoomable timeline and map arrive in Phase 7. */
export function EventsPage() {
  const caseRef = useCurrentCase()
  const { canReview } = useCaseAccess(caseRef)
  const timeZone = useCaseTimeZone(caseRef)
  const [type, setType] = useState<EventType | typeof ALL>(ALL)
  const [entity, setEntity] = useState<string>(ALL)
  const [review, setReview] = useState<ReviewStatus | typeof ALL>(ALL)
  const { data: entities } = useEntities(caseRef)
  const query = {
    event_type: type === ALL ? undefined : type,
    entity: entity === ALL ? undefined : entity,
    review_status: review === ALL ? undefined : review,
  }
  const { data, isPending, isError, error, refetch, isFetching } = useEvents(caseRef, query)

  if (!caseRef) {
    return (
      <div className="mx-auto max-w-3xl pt-6">
        <EmptyState icon={FolderSearch} title="No investigation selected" description="Choose an investigation in the top bar."
          action={<Button asChild variant="outline"><Link to="/investigations">Open investigations</Link></Button>} />
      </div>
    )
  }
  const filtered = Boolean(query.event_type || query.entity || query.review_status)
  const days = groupByDay(data?.items ?? [], timeZone)

  return (
    <div className="mx-auto max-w-5xl space-y-5">
      <PageHeader
        eyebrow={<IdTag>{caseRef}</IdTag>}
        title="Events"
        description={`Things that happened, in time order. Each one links to the evidence that supports it. Times are shown in the investigation's time zone: ${zoneLabel(timeZone)}.`}
      />

      <div className="flex flex-wrap items-center gap-2">
        <Select value={type} onValueChange={(v) => setType(v as EventType | typeof ALL)}>
          <SelectTrigger className="w-52" aria-label="Filter by event type"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>All event types</SelectItem>
            {Object.entries(eventTypeTerms).map(([value, term]) => (
              <SelectItem key={value} value={value}><term.icon /> {term.label}</SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select value={entity} onValueChange={setEntity}>
          <SelectTrigger className="w-64" aria-label="Filter by entity"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>Any entity</SelectItem>
            {entities?.items.map((e) => (
              <SelectItem key={e.reference} value={e.reference}>{e.reference} · {e.label}</SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select value={review} onValueChange={(v) => setReview(v as ReviewStatus | typeof ALL)}>
          <SelectTrigger className="w-44" aria-label="Filter by review"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>Any review status</SelectItem>
            {Object.entries(reviewStatusTerms).map(([value, term]) => (
              <SelectItem key={value} value={value}>{term.label}</SelectItem>
            ))}
          </SelectContent>
        </Select>
        {data && <span className="text-sm text-muted-foreground">{data.total} event{data.total === 1 ? '' : 's'}</span>}
      </div>

      {isError ? (
        <ErrorState description={error instanceof ApiError ? error.message : 'Events could not be loaded.'} onRetry={() => refetch()} retrying={isFetching} />
      ) : isPending ? (
        <Skeleton className="h-96 w-full" />
      ) : data.total === 0 ? (
        filtered ? (
          <EmptyState icon={SearchX} title="No events match these filters" description="Try a different filter." />
        ) : (
          <EmptyState icon={Activity} title="No events yet" description="Events are created when evidence is processed, or when analysts record what they see." />
        )
      ) : (
        <div className="space-y-4">
          {days.map(([day, events]) => (
            <Card key={day} className="py-2">
              <CardContent>
                <h2 className="border-b py-2 text-sm font-semibold">{day}</h2>
                <ol className="divide-y">
                  {events.map((event) => (
                    <EventRow key={event.reference} event={event} caseRef={caseRef} canReview={canReview} />
                  ))}
                </ol>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}

/** Days are the investigation's days: 23:30 in India is not "tomorrow" because a viewer is elsewhere. */
function groupByDay(events: InvestigationEvent[], timeZone: string): [string, InvestigationEvent[]][] {
  const groups = new Map<string, InvestigationEvent[]>()
  for (const event of events) {
    const day = event.occurredAt ? dayInZone(event.occurredAt, timeZone) : 'Time unknown'
    groups.set(day, [...(groups.get(day) ?? []), event])
  }
  return [...groups.entries()]
}
