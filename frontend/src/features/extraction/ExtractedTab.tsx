import { useState } from 'react'
import { Plus, ScanSearch } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { useExtracted } from '@/services/queries'
import { AssertionLabel } from '@/design-system/badges'
import { ConfidenceIndicator } from '@/design-system/ConfidenceIndicator'
import { EmptyState, ErrorState } from '@/design-system/states'
import { AnnotationDialog } from './AnnotationDialog'
import { ContextSnippet, EntityChip, EventRow } from './components'
import { useCaseAccess } from './useCaseAccess'

/** Evidence → Extracted information → Entity / Event (plan §12 navigation chain). */
export function ExtractedTab({ caseRef, evidenceRef, processing }: { caseRef: string; evidenceRef: string; processing: boolean }) {
  const { data, isPending, isError, refetch, isFetching } = useExtracted(caseRef, evidenceRef, !processing)
  const { canReview, canContribute } = useCaseAccess(caseRef)
  const [annotating, setAnnotating] = useState(false)

  if (processing) {
    return <EmptyState icon={ScanSearch} title="Still processing" description="Extracted information appears here when processing finishes." />
  }
  if (isPending) return <Skeleton className="h-64 w-full" />
  if (isError) return <ErrorState description="Extracted information could not be loaded." onRetry={() => refetch()} retrying={isFetching} />

  return (
    <div className="grid gap-6 lg:grid-cols-5">
      <Card className="lg:col-span-2">
        <CardHeader>
          <CardTitle>Entities found</CardTitle>
          <CardDescription>{data.mentions.length} mention{data.mentions.length === 1 ? '' : 's'} in this evidence</CardDescription>
        </CardHeader>
        <CardContent>
          {data.mentions.length === 0 ? (
            <p className="text-sm text-muted-foreground">No entities were found in this evidence.</p>
          ) : (
            <ul className="space-y-3">
              {data.mentions.map((m, i) => (
                <li key={i} className="space-y-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <EntityChip entity={m.entity} caseRef={caseRef} />
                    <AssertionLabel kind={m.assertionKind} />
                    <ConfidenceIndicator score={m.confidence} />
                  </div>
                  <p className="text-xs text-muted-foreground">{m.sourceLocation} · <span className="font-mono">{m.extractor}</span></p>
                  <ContextSnippet text={m.context} />
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
      <Card className="lg:col-span-3">
        <CardHeader>
          <CardTitle>Events from this evidence</CardTitle>
          <CardDescription>Automatic results and analyst observations.</CardDescription>
          {canContribute && (
            <CardAction>
              <Button variant="outline" size="sm" onClick={() => setAnnotating(true)}><Plus /> Record observation</Button>
            </CardAction>
          )}
        </CardHeader>
        <CardContent>
          {data.events.length === 0 ? (
            <p className="text-sm text-muted-foreground">No events yet.</p>
          ) : (
            <ol className="divide-y">
              {data.events.map((event) => (
                <EventRow key={event.reference} event={event} caseRef={caseRef} canReview={canReview} showEvidence={false} />
              ))}
            </ol>
          )}
        </CardContent>
      </Card>
      <AnnotationDialog caseRef={caseRef} evidenceRef={evidenceRef} open={annotating} onOpenChange={setAnnotating} />
    </div>
  )
}
