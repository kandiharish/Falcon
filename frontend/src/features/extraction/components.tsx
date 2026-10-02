/**
 * Building blocks shared by the Entities, Events and Evidence screens.
 * Every fact shows: what it is · where it came from · how it was found · how sure · reviewed?
 */
import { Link } from 'react-router'
import { Check, MapPin, X } from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import type { EntityRef, InvestigationEvent, ReviewStatus } from '@/domain/types'
import { ApiError } from '@/services/apiClient'
import { useReview } from '@/services/queries'
import { AssertionLabel, StatusBadge } from '@/design-system/badges'
import { ConfidenceIndicator } from '@/design-system/ConfidenceIndicator'
import { entityTypeTerms, eventTypeTerms, participantRoleLabels } from '@/design-system/vocabulary'
import { formatDateTime } from '@/lib/format'
import { cn } from '@/lib/utils'

export function EntityChip({ entity, caseRef, role }: { entity: EntityRef; caseRef: string; role?: string }) {
  const term = entityTypeTerms[entity.entityType]
  return (
    <Link
      to={`/investigations/${caseRef}/entities/${entity.reference}`}
      className="inline-flex max-w-full items-center gap-1 rounded-md border bg-card px-1.5 py-0.5 text-xs outline-none hover:border-primary/50 hover:bg-accent focus-visible:ring-2 focus-visible:ring-ring"
      title={`${term.label} ${entity.reference}`}
    >
      <term.icon aria-hidden className="size-3.5 shrink-0 text-muted-foreground" />
      <span className="font-mono text-[0.7rem] text-muted-foreground">{entity.reference}</span>
      <span className="truncate font-medium">{entity.label}</span>
      {role && <span className="text-muted-foreground">· {participantRoleLabels[role] ?? role}</span>}
    </Link>
  )
}

export function EvidenceChip({ reference, caseRef }: { reference: string; caseRef: string }) {
  return (
    <Link
      to={`/investigations/${caseRef}/evidence/${reference}`}
      className="inline-flex items-center rounded border bg-muted/60 px-1.5 font-mono text-[0.72rem] font-medium outline-none hover:border-primary/50 focus-visible:ring-2 focus-visible:ring-ring"
      title="Open the supporting evidence"
    >
      {reference}
    </Link>
  )
}

/** "…the van [ZZ99 ZZ 0001] left…" with the found text highlighted. */
export function ContextSnippet({ text }: { text: string }) {
  if (!text) return null
  const match = /^(.*?)\[(.+?)\](.*)$/s.exec(text)
  if (!match) return <q className="text-xs text-muted-foreground">{text}</q>
  return (
    <q className="text-xs text-muted-foreground">
      {match[1]}
      <mark className="rounded bg-signal/20 px-0.5 text-foreground">{match[2]}</mark>
      {match[3]}
    </q>
  )
}

export function ReviewActions({
  caseRef,
  kind,
  reference,
  status,
  size = 'sm',
}: {
  caseRef: string
  kind: 'entity' | 'event'
  reference: string
  status: ReviewStatus
  size?: 'sm' | 'xs'
}) {
  const review = useReview(caseRef)
  const decide = (next: ReviewStatus) =>
    review.mutate(
      { kind, reference, status: next },
      {
        onSuccess: () =>
          toast.success(
            next === 'confirmed' ? `${reference} confirmed` : next === 'rejected' ? `${reference} rejected` : `${reference} reset to review`,
          ),
        onError: (err) => toast.error('Review failed', { description: err instanceof ApiError ? err.message : undefined }),
      },
    )
  if (status !== 'pending') {
    return (
      <Button variant="ghost" size={size} disabled={review.isPending} onClick={() => decide('pending')}>
        Undo review
      </Button>
    )
  }
  return (
    <div className="flex gap-1">
      <Button variant="outline" size={size} disabled={review.isPending} onClick={() => decide('confirmed')}>
        <Check /> Confirm
      </Button>
      <Button variant="ghost" size={size} disabled={review.isPending} onClick={() => decide('rejected')}>
        <X /> Reject
      </Button>
    </div>
  )
}

/** One event: time · what happened · who/what took part · supporting evidence · provenance. */
export function EventRow({
  event,
  caseRef,
  canReview,
  showEvidence = true,
}: {
  event: InvestigationEvent
  caseRef: string
  canReview: boolean
  showEvidence?: boolean
}) {
  const term = eventTypeTerms[event.eventType]
  return (
    <li className={cn('flex gap-3 py-3', event.reviewStatus === 'rejected' && 'opacity-55')}>
      <div className="w-24 shrink-0 text-right">
        {event.occurredAt ? (
          <>
            <p className="font-mono text-sm tabular-nums">
              {new Date(event.occurredAt).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
            </p>
            <p className="text-[0.7rem] text-muted-foreground">
              {new Date(event.occurredAt).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })}
            </p>
          </>
        ) : (
          <p className="text-xs text-muted-foreground">time unknown</p>
        )}
      </div>
      <div className="flex size-8 shrink-0 items-center justify-center rounded-full bg-muted">
        <term.icon aria-hidden className="size-4 text-muted-foreground" />
      </div>
      <div className="min-w-0 flex-1 space-y-1.5">
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
          <span className="font-mono text-xs text-muted-foreground">{event.reference}</span>
          <span className="text-sm font-medium">{term.label}</span>
          <AssertionLabel kind={event.assertionKind} />
          <ConfidenceIndicator score={event.confidence} />
          <StatusBadge kind="review" status={event.reviewStatus} />
        </div>
        <p className="text-sm">{event.description}</p>
        {(event.participants.length > 0 || showEvidence || event.locationText || event.latitude !== null) && (
          <div className="flex flex-wrap items-center gap-1.5">
            {event.participants.map((p) => (
              <EntityChip key={`${p.reference}-${p.role}`} entity={p} caseRef={caseRef} role={p.role} />
            ))}
            {(event.locationText || event.latitude !== null) && (
              <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
                <MapPin aria-hidden className="size-3.5" />
                {event.locationText || `${event.latitude?.toFixed(5)}, ${event.longitude?.toFixed(5)}`}
              </span>
            )}
            {showEvidence && (
              <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
                from <EvidenceChip reference={event.evidenceReference} caseRef={caseRef} />
                {event.sourceLocation && <span>· {event.sourceLocation}</span>}
              </span>
            )}
          </div>
        )}
        {event.endedAt && event.occurredAt && (
          <p className="text-xs text-muted-foreground">Until {formatDateTime(event.endedAt)}</p>
        )}
      </div>
      {canReview && (
        <div className="shrink-0">
          <ReviewActions caseRef={caseRef} kind="event" reference={event.reference} status={event.reviewStatus} size="xs" />
        </div>
      )}
    </li>
  )
}
