import { Copy, FileSearch, RefreshCw } from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { ApiError } from '@/services/apiClient'
import { useReindex, useSimilarEvidence } from '@/services/queries'
import { AssertionLabel } from '@/design-system/badges'
import { EmptyState, ErrorState } from '@/design-system/states'
import { EvidenceChip } from '@/features/extraction/components'
import { useCaseAccess } from '@/features/extraction/useCaseAccess'
import { AIAssistedLabel } from './components'

/** Evidence workspace tab: near-duplicate pictures and documents that say similar things. */
export function SimilarTab({ caseRef, evidenceRef }: { caseRef: string; evidenceRef: string }) {
  const { data, isPending, isError, error, refetch, isFetching } = useSimilarEvidence(caseRef, evidenceRef)
  const { canContribute } = useCaseAccess(caseRef)
  const reindex = useReindex(caseRef)
  const rebuild = () =>
    reindex.mutate(undefined, {
      onSuccess: (r) => toast.success('AI index rebuilt', { description: `${plural(r.documents, 'document')} (${plural(r.chunks, 'passage')}) and ${plural(r.images, 'image')} indexed.` }),
      onError: (err) => toast.error('Could not rebuild the AI index', { description: err instanceof ApiError ? err.message : undefined }),
    })

  const toolbar = (
    <div className="flex flex-wrap items-center justify-between gap-2">
      <p className="text-sm text-muted-foreground">
        Pictures are compared by a fingerprint (no AI). Text is compared by meaning with the local AI model. Similar is not the same: check both items.
      </p>
      {canContribute && (
        <Button size="sm" variant="outline" onClick={rebuild} disabled={reindex.isPending}>
          <RefreshCw className={reindex.isPending ? 'animate-spin' : undefined} /> Rebuild AI index
        </Button>
      )}
    </div>
  )

  if (isError) return <ErrorState description={error instanceof ApiError ? error.message : 'Similar evidence could not be loaded.'} onRetry={() => refetch()} retrying={isFetching} />
  if (isPending) return <Skeleton className="h-40 w-full" />
  return (
    <div className="space-y-4">
      {toolbar}
      {data.length === 0 ? (
        <EmptyState icon={FileSearch} title="No similar evidence" description="No near-duplicate picture and no document with similar text was found in this investigation." />
      ) : (
        <ul className="space-y-3">
          {data.map((s) => (
            <li key={`${s.kind}-${s.evidence.reference}`} className="space-y-2 rounded-lg border bg-card p-4">
              <div className="flex flex-wrap items-center gap-2">
                {s.kind === 'image' ? <Copy aria-hidden className="size-4 text-muted-foreground" /> : <FileSearch aria-hidden className="size-4 text-muted-foreground" />}
                <EvidenceChip reference={s.evidence.reference} caseRef={caseRef} />
                <span className="truncate text-sm">{s.evidence.description}</span>
                <span className="ml-auto font-mono text-xs text-muted-foreground">similarity {s.score.toFixed(2)}</span>
                {s.kind === 'image' ? <AssertionLabel kind="detected" /> : <AIAssistedLabel />}
              </div>
              <p className="text-sm text-muted-foreground">{s.explanation}</p>
              {s.kind === 'text' && (
                <div className="grid gap-2 text-sm sm:grid-cols-2">
                  <blockquote className="border-l-2 pl-3"><span className="block text-xs text-muted-foreground">{evidenceRef}</span>{s.passage}</blockquote>
                  <blockquote className="border-l-2 pl-3"><span className="block text-xs text-muted-foreground">{s.evidence.reference}</span>{s.match}</blockquote>
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

const plural = (count: number, word: string) => `${count} ${word}${count === 1 ? '' : 's'}`
