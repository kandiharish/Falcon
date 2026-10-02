import { useState } from 'react'
import { Link, useParams } from 'react-router'
import { ArrowLeft, Check, Info, ShieldAlert, Undo2, Waypoints, X } from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Label } from '@/components/ui/label'
import { Skeleton } from '@/components/ui/skeleton'
import { Textarea } from '@/components/ui/textarea'
import type { CorrelationDetail, CorrelationFactor, ReviewStatus } from '@/domain/types'
import { ApiError } from '@/services/apiClient'
import { useCorrelation, useReviewCorrelation } from '@/services/queries'
import { StatusBadge } from '@/design-system/badges'
import { IdTag } from '@/design-system/IdTag'
import { PageHeader } from '@/design-system/PageHeader'
import { EmptyState, ErrorState } from '@/design-system/states'
import { formatInZone } from '@/lib/time'
import { EventRow } from '@/features/extraction/components'
import { useCaseAccess, useCaseTimeZone } from '@/features/extraction/useCaseAccess'
import { EvidencePair, LevelBadge, StaleBadge } from './components'
import { factorTerms } from './terms'

/** "Why this relationship exists" (plan §19): every factor, its weight, and the events behind it. */
export function CorrelationDetailPage() {
  const { reference: caseRef = '', correlationRef = '' } = useParams()
  const { data: correlation, isPending, isError, error, refetch, isFetching } = useCorrelation(caseRef, correlationRef)
  const { canReview, canCorrelate } = useCaseAccess(caseRef)

  if (isPending) return <div className="mx-auto max-w-5xl space-y-4"><Skeleton className="h-8 w-1/3" /><Skeleton className="h-64 w-full" /></div>
  if (isError) {
    return (
      <div className="mx-auto max-w-3xl pt-6">
        {error instanceof ApiError && error.status === 404 ? (
          <EmptyState icon={Waypoints} title="Correlation not found" description={error.message}
            action={<Button asChild variant="outline"><Link to="/correlations">Back to correlations</Link></Button>} />
        ) : (
          <ErrorState description="The correlation could not be loaded." onRetry={() => refetch()} retrying={isFetching} />
        )}
      </div>
    )
  }

  const entity = correlation.factors.find((f) => f.kind === 'entity')
  const shared = (entity?.details.shared ?? []) as { reference: string; label: string; confidence: number }[]

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <Button asChild variant="ghost" size="sm" className="-ml-2 text-muted-foreground">
        <Link to="/correlations"><ArrowLeft /> Correlations</Link>
      </Button>

      <PageHeader
        eyebrow={
          <span className="flex flex-wrap items-center gap-2">
            <IdTag>{correlation.reference}</IdTag>
            <LevelBadge level={correlation.level} score={correlation.score} />
            <StatusBadge kind="review" status={correlation.reviewStatus} />
            {correlation.stale && <StaleBadge />}
          </span>
        }
        title={`${correlation.evidenceA.reference} ⟷ ${correlation.evidenceB.reference}`}
        description="A potential relationship between two evidence items."
      />

      <Card className="py-4">
        <CardContent><EvidencePair correlation={correlation} caseRef={caseRef} /></CardContent>
      </Card>

      <p className="flex items-start gap-2 rounded-md border border-warning/30 bg-warning/8 px-3 py-2 text-sm">
        <ShieldAlert aria-hidden className="mt-0.5 size-4 shrink-0 text-warning" />
        <span>
          This is a <strong>potential relationship, not proof</strong>. It was found by fixed rules ({correlation.algorithm}) from the
          extracted information below. Check the supporting evidence before relying on it.
        </span>
      </p>

      {correlation.stale && (
        <p className="flex items-start gap-2 rounded-md border px-3 py-2 text-sm text-muted-foreground">
          <Info aria-hidden className="mt-0.5 size-4 shrink-0" />
          The evidence has changed since this was reviewed and the engine no longer finds this relationship. The reasons below are from the last time it was found; the review decision is kept for the record.
        </p>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Why this relationship exists</CardTitle>
          <CardDescription>Each factor is scored 0–1 and multiplied by its weight. The contributions add up to the score.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <ol className="space-y-4">
            {correlation.factors.map((f) => <FactorBreakdown key={f.kind} factor={f} />)}
          </ol>
          <div className="flex items-center justify-between border-t pt-3 text-sm">
            <span className="font-medium">Score</span>
            <span className="font-mono tabular-nums">
              {correlation.factors.length > 1 && `${correlation.factors.map((f) => f.contribution.toFixed(2)).join(' + ')} = `}
              <strong>{correlation.score.toFixed(2)}</strong>
            </span>
          </div>
          <p className="text-xs text-muted-foreground">High ≥ 0.75 · Medium ≥ 0.50 · Low below. Factors that score 0 are not listed.</p>
        </CardContent>
      </Card>

      {shared.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Shared entities</CardTitle>
            <CardDescription>Found in both evidence items. The confidence is the weaker of the two sightings.</CardDescription>
          </CardHeader>
          <CardContent>
            <ul className="divide-y">
              {shared.map((s) => (
                <li key={s.reference} className="flex items-center gap-3 py-2 text-sm">
                  <Link to={`/investigations/${caseRef}/entities/${s.reference}`} className="font-mono text-xs text-primary underline-offset-4 hover:underline">
                    {s.reference}
                  </Link>
                  <span className="min-w-0 flex-1 truncate font-medium">{s.label}</span>
                  <span className="font-mono text-xs text-muted-foreground tabular-nums">{s.confidence.toFixed(2)}</span>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}

      {correlation.supportingEvents.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Supporting events</CardTitle>
            <CardDescription>The two events closest in time and place, one from each evidence item.</CardDescription>
          </CardHeader>
          <CardContent>
            <ol className="divide-y">
              {correlation.supportingEvents.map((event) => (
                <EventRow key={event.reference} event={event} caseRef={caseRef} canReview={canReview} />
              ))}
            </ol>
          </CardContent>
        </Card>
      )}

      <ReviewCard correlation={correlation} caseRef={caseRef} canReview={canCorrelate} />
    </div>
  )
}

function FactorBreakdown({ factor }: { factor: CorrelationFactor }) {
  const term = factorTerms[factor.kind]
  return (
    <li className="grid gap-2 sm:grid-cols-[12rem_minmax(0,1fr)]">
      <div className="flex items-start gap-2">
        <span className="flex size-8 shrink-0 items-center justify-center rounded-full bg-muted">
          <term.icon aria-hidden className="size-4 text-muted-foreground" />
        </span>
        <div>
          <p className="text-sm font-medium">{term.label}</p>
          <p className="font-mono text-xs text-muted-foreground tabular-nums">
            {factor.score.toFixed(2)} × {factor.weight.toFixed(2)} = {factor.contribution.toFixed(2)}
          </p>
        </div>
      </div>
      <div className="space-y-1.5">
        <div className="h-2 overflow-hidden rounded-full bg-muted" role="img" aria-label={`Factor score ${factor.score.toFixed(2)} of 1`}>
          <div className="h-full rounded-full bg-primary" style={{ width: `${Math.round(factor.score * 100)}%` }} />
        </div>
        <p className="text-sm">{factor.explanation}</p>
        <p className="text-xs text-muted-foreground">{term.question}</p>
      </div>
    </li>
  )
}

function ReviewCard({ correlation, caseRef, canReview }: { correlation: CorrelationDetail; caseRef: string; canReview: boolean }) {
  const timeZone = useCaseTimeZone(caseRef)
  const review = useReviewCorrelation(caseRef, correlation.reference)
  const [note, setNote] = useState('')
  const decide = (status: ReviewStatus) =>
    review.mutate(
      { status, note: note.trim() || undefined },
      {
        onSuccess: () => {
          setNote('')
          toast.success(status === 'pending' ? `${correlation.reference} back to review` : `${correlation.reference} ${status}`)
        },
        onError: (err) => toast.error('Review failed', { description: err instanceof ApiError ? err.message : undefined }),
      },
    )

  return (
    <Card>
      <CardHeader>
        <CardTitle>Analyst review</CardTitle>
        <CardDescription>Confirm if the evidence supports the relationship; reject (with a reason) if it does not. Every decision is audited.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {correlation.reviewStatus !== 'pending' && (
          <div className="space-y-1 rounded-md border bg-muted/40 px-3 py-2 text-sm">
            <p className="flex flex-wrap items-center gap-2">
              <StatusBadge kind="review" status={correlation.reviewStatus} />
              by <strong>{correlation.reviewedBy ?? 'unknown'}</strong>
              {correlation.reviewedAt && (
                <span className="text-muted-foreground">· {formatInZone(correlation.reviewedAt, timeZone, { dateStyle: 'medium', timeStyle: 'short' })}</span>
              )}
            </p>
            {correlation.reviewNote && <p className="text-muted-foreground">“{correlation.reviewNote}”</p>}
          </div>
        )}
        {!canReview ? (
          <p className="text-sm text-muted-foreground">Only reviewers on this investigation's team can confirm or reject correlations.</p>
        ) : correlation.reviewStatus === 'pending' ? (
          <>
            <div className="space-y-1.5">
              <Label htmlFor="review-note">Note <span className="font-normal text-muted-foreground">(required to reject)</span></Label>
              <Textarea id="review-note" value={note} maxLength={1000} onChange={(e) => setNote(e.target.value)}
                placeholder="e.g. Same van seen by both cameras; plate matches." />
            </div>
            <div className="flex flex-wrap gap-2">
              <Button onClick={() => decide('confirmed')} disabled={review.isPending}><Check /> Confirm relationship</Button>
              <Button variant="outline" onClick={() => decide('rejected')} disabled={review.isPending || !note.trim()}
                title={note.trim() ? undefined : 'Write a reason first'}>
                <X /> Reject
              </Button>
            </div>
          </>
        ) : (
          <Button variant="ghost" size="sm" onClick={() => decide('pending')} disabled={review.isPending}><Undo2 /> Undo review</Button>
        )}
      </CardContent>
    </Card>
  )
}
