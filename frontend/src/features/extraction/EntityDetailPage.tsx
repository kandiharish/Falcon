import { Link, useParams } from 'react-router'
import { ArrowLeft, CalendarClock, FileStack, Fingerprint, UserRoundSearch } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import type { Mention } from '@/domain/types'
import { ApiError } from '@/services/apiClient'
import { useEntity } from '@/services/queries'
import { AssertionLabel, StatusBadge } from '@/design-system/badges'
import { ConfidenceIndicator } from '@/design-system/ConfidenceIndicator'
import { IdTag } from '@/design-system/IdTag'
import { PageHeader } from '@/design-system/PageHeader'
import { EmptyState, ErrorState } from '@/design-system/states'
import { entityTypeTerms } from '@/design-system/vocabulary'
import { ContextSnippet, EventRow, EvidenceChip, ReviewActions } from './components'
import { useCaseAccess } from './useCaseAccess'

/** Entity profile (plan §15): where it appears, what it took part in, and how we know. */
export function EntityDetailPage() {
  const { reference: caseRef = '', entityRef = '' } = useParams()
  const { data: entity, isPending, isError, error, refetch, isFetching } = useEntity(caseRef, entityRef)
  const { canReview } = useCaseAccess(caseRef)

  if (isPending) return <div className="mx-auto max-w-7xl space-y-4"><Skeleton className="h-8 w-1/3" /><Skeleton className="h-64 w-full" /></div>
  if (isError) {
    return (
      <div className="mx-auto max-w-3xl pt-6">
        {error instanceof ApiError && error.status === 404 ? (
          <EmptyState icon={UserRoundSearch} title="Entity not found" description={error.message}
            action={<Button asChild variant="outline"><Link to="/entities">Back to entities</Link></Button>} />
        ) : (
          <ErrorState description="The entity could not be loaded." onRetry={() => refetch()} retrying={isFetching} />
        )}
      </div>
    )
  }

  const term = entityTypeTerms[entity.entityType]
  const byEvidence = groupBy(entity.mentions, (m) => m.evidenceReference)

  return (
    <div className="mx-auto max-w-7xl space-y-6">
      <Button asChild variant="ghost" size="sm" className="-ml-2 text-muted-foreground">
        <Link to="/entities"><ArrowLeft /> Entities</Link>
      </Button>

      <PageHeader
        eyebrow={
          <span className="flex flex-wrap items-center gap-2">
            <IdTag>{entity.reference}</IdTag>
            <span className="inline-flex items-center gap-1"><term.icon aria-hidden className="size-3.5" /> {term.label}</span>
            <StatusBadge kind="review" status={entity.reviewStatus} />
          </span>
        }
        title={entity.label}
        description={`Appears in ${entity.evidenceCount} evidence item${entity.evidenceCount === 1 ? '' : 's'} and ${entity.eventCount} event${entity.eventCount === 1 ? '' : 's'}.`}
        actions={canReview && <ReviewActions caseRef={caseRef} kind="entity" reference={entity.reference} status={entity.reviewStatus} />}
      />

      <div className="grid gap-4 sm:grid-cols-3">
        <Stat icon={FileStack} label="Evidence items" value={entity.evidenceCount} />
        <Stat icon={Fingerprint} label="Mentions" value={entity.mentionCount} />
        <Stat icon={CalendarClock} label="Events" value={entity.eventCount} />
      </div>

      <div className="grid gap-6 lg:grid-cols-5">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Evidence references</CardTitle>
            <CardDescription>Every place this {term.label.toLowerCase()} was found, and how.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {Object.entries(byEvidence).map(([evidenceRef, mentions]) => (
              <div key={evidenceRef} className="space-y-2 rounded-md border p-3">
                <div className="flex items-center gap-2">
                  <EvidenceChip reference={evidenceRef} caseRef={caseRef} />
                  <span className="truncate text-sm">{mentions[0].evidenceDescription}</span>
                </div>
                <ul className="space-y-2">
                  {mentions.map((m, i) => <MentionRow key={i} mention={m} />)}
                </ul>
              </div>
            ))}
          </CardContent>
        </Card>

        <Card className="lg:col-span-3">
          <CardHeader>
            <CardTitle>Events</CardTitle>
            <CardDescription>What this {term.label.toLowerCase()} took part in, in time order.</CardDescription>
          </CardHeader>
          <CardContent>
            {entity.events.length === 0 ? (
              <p className="text-sm text-muted-foreground">No events involve this entity yet.</p>
            ) : (
              <ol className="divide-y">
                {entity.events.map((event) => (
                  <EventRow key={event.reference} event={event} caseRef={caseRef} canReview={canReview} />
                ))}
              </ol>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

function MentionRow({ mention }: { mention: Mention }) {
  return (
    <li className="space-y-1 text-sm">
      <div className="flex flex-wrap items-center gap-2">
        <AssertionLabel kind={mention.assertionKind} />
        <ConfidenceIndicator score={mention.confidence} />
        <span className="font-mono text-[0.7rem] text-muted-foreground">{mention.extractor}</span>
      </div>
      <p className="text-xs text-muted-foreground">{mention.sourceLocation}</p>
      <ContextSnippet text={mention.context} />
    </li>
  )
}

function Stat({ icon: Icon, label, value }: { icon: typeof FileStack; label: string; value: number }) {
  return (
    <Card className="py-4">
      <CardContent className="flex items-center gap-3">
        <Icon aria-hidden className="size-5 text-muted-foreground" />
        <div>
          <p className="font-mono text-xl tabular-nums">{value}</p>
          <p className="text-xs text-muted-foreground">{label}</p>
        </div>
      </CardContent>
    </Card>
  )
}

function groupBy<T>(items: T[], key: (item: T) => string): Record<string, T[]> {
  const groups: Record<string, T[]> = {}
  for (const item of items) (groups[key(item)] ??= []).push(item)
  return groups
}
