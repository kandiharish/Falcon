import { Waypoints } from 'lucide-react'
import { Skeleton } from '@/components/ui/skeleton'
import { ApiError } from '@/services/apiClient'
import { useCorrelations } from '@/services/queries'
import { EmptyState, ErrorState } from '@/design-system/states'
import { CorrelationRow } from './components'

/** Evidence workspace tab: the other evidence this item may be related to. */
export function CorrelationsTab({ caseRef, evidenceRef }: { caseRef: string; evidenceRef: string }) {
  const { data, isPending, isError, error, refetch, isFetching } = useCorrelations(caseRef, { evidence: evidenceRef })
  if (isError) {
    return <ErrorState description={error instanceof ApiError ? error.message : 'Correlations could not be loaded.'} onRetry={() => refetch()} retrying={isFetching} />
  }
  if (isPending) return <Skeleton className="h-48 w-full" />
  if (data.total === 0) {
    return <EmptyState icon={Waypoints} title="No correlations" description="No other evidence shares an entity with this item, or has events close to it in time and place." />
  }
  return (
    <ol className="divide-y rounded-lg border bg-card px-4">
      {data.items.map((c) => <CorrelationRow key={c.reference} correlation={c} caseRef={caseRef} />)}
    </ol>
  )
}
