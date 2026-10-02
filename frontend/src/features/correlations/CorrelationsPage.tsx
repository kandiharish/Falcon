import { useState } from 'react'
import { Link } from 'react-router'
import { FolderSearch, RefreshCw, SearchX, ShieldAlert, Waypoints } from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Checkbox } from '@/components/ui/checkbox'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import type { CorrelationLevel, ReviewStatus } from '@/domain/types'
import { ApiError } from '@/services/apiClient'
import { useCorrelations, useRunCorrelation } from '@/services/queries'
import { IdTag } from '@/design-system/IdTag'
import { PageHeader } from '@/design-system/PageHeader'
import { EmptyState, ErrorState } from '@/design-system/states'
import { reviewStatusTerms } from '@/design-system/vocabulary'
import { useCaseAccess, useCurrentCase } from '@/features/extraction/useCaseAccess'
import { CorrelationRow } from './components'
import { levelTerms } from './terms'

const ALL = 'all'

/** Potential relationships between evidence items (plan §18–§19), strongest first. */
export function CorrelationsPage() {
  const caseRef = useCurrentCase()
  const { canCorrelate } = useCaseAccess(caseRef)
  const [level, setLevel] = useState<CorrelationLevel | typeof ALL>(ALL)
  const [review, setReview] = useState<ReviewStatus | typeof ALL>(ALL)
  const [showStale, setShowStale] = useState(true)
  const query = {
    level: level === ALL ? undefined : level,
    review_status: review === ALL ? undefined : review,
    include_stale: showStale ? undefined : false,
  }
  const { data, isPending, isError, error, refetch, isFetching } = useCorrelations(caseRef, query)
  const run = useRunCorrelation(caseRef ?? '')

  if (!caseRef) {
    return (
      <div className="mx-auto max-w-3xl pt-6">
        <EmptyState icon={FolderSearch} title="No investigation selected" description="Choose an investigation in the top bar."
          action={<Button asChild variant="outline"><Link to="/investigations">Open investigations</Link></Button>} />
      </div>
    )
  }

  const runNow = () =>
    run.mutate(undefined, {
      onSuccess: (r) =>
        toast.success('Correlation finished', {
          description: `${r.total} relationship${r.total === 1 ? '' : 's'} · ${r.created} new · ${r.updated} changed · ${r.removed} removed · ${r.stale} no longer found`,
        }),
      onError: (err) => toast.error('Correlation failed', { description: err instanceof ApiError ? err.message : undefined }),
    })
  const filtered = Boolean(query.level || query.review_status || query.include_stale === false)

  return (
    <div className="mx-auto max-w-5xl space-y-5">
      <PageHeader
        eyebrow={<IdTag>{caseRef}</IdTag>}
        title="Correlations"
        description="Pairs of evidence that may be related because they share an entity, or because their events happened close together in time and place. Open one to see why it was found."
        actions={
          canCorrelate && (
            <Button variant="outline" onClick={runNow} disabled={run.isPending}>
              <RefreshCw className={run.isPending ? 'animate-spin' : undefined} /> Run correlation
            </Button>
          )
        }
      />

      <p className="flex items-start gap-2 rounded-md border border-warning/30 bg-warning/8 px-3 py-2 text-sm">
        <ShieldAlert aria-hidden className="mt-0.5 size-4 shrink-0 text-warning" />
        <span>
          A correlation is a <strong>potential</strong> relationship found by rules, not proof. An analyst must confirm or reject each one.
          Correlation re-runs automatically when evidence is processed or reviewed.
        </span>
      </p>

      <div className="flex flex-wrap items-center gap-3">
        <Select value={level} onValueChange={(v) => setLevel(v as CorrelationLevel | typeof ALL)}>
          <SelectTrigger className="w-40" aria-label="Filter by strength"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>Any strength</SelectItem>
            {Object.entries(levelTerms).map(([value, term]) => (
              <SelectItem key={value} value={value}>{term.label}</SelectItem>
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
        <div className="flex items-center gap-2">
          <Checkbox id="show-stale" checked={showStale} onCheckedChange={(v) => setShowStale(v === true)} />
          <Label htmlFor="show-stale" className="font-normal">Show “no longer found”</Label>
        </div>
        {data && <span className="text-sm text-muted-foreground">{data.total} correlation{data.total === 1 ? '' : 's'}</span>}
      </div>

      {isError ? (
        <ErrorState description={error instanceof ApiError ? error.message : 'Correlations could not be loaded.'} onRetry={() => refetch()} retrying={isFetching} />
      ) : isPending ? (
        <Skeleton className="h-96 w-full" />
      ) : data.total === 0 ? (
        filtered ? (
          <EmptyState icon={SearchX} title="No correlations match these filters" description="Try a different filter." />
        ) : (
          <EmptyState icon={Waypoints} title="No correlations yet" description="Correlations appear when two evidence items share an entity, or have events close in time and place." />
        )
      ) : (
        <Card className="py-2">
          <CardContent>
            <ol className="divide-y">
              {data.items.map((c) => (
                <CorrelationRow key={c.reference} correlation={c} caseRef={caseRef} />
              ))}
            </ol>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
