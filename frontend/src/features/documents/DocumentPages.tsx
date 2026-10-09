/**
 * Pages for drafted documents: a Section 63 certificate for one evidence item, and a
 * requisition letter suggested by an insight. Both are drafts: printed, checked, then signed.
 */
import type { ReactNode } from 'react'
import { Link, useParams, useSearchParams } from 'react-router'
import { ArrowLeft, FileWarning, Printer } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { ApiError } from '@/services/apiClient'
import type { DraftDocument, LetterKind } from '@/services/documentsService'
import { useCertificate, useLetter } from '@/services/queries'
import { EmptyState, ErrorState } from '@/design-system/states'
import { DraftDocumentView } from './DraftDocumentView'

export function CertificatePage() {
  const { reference: caseRef = '', evidenceRef = '' } = useParams()
  const query = useCertificate(caseRef, evidenceRef)
  return (
    <DocumentShell back={<Link to={`/investigations/${caseRef}/evidence/${evidenceRef}`}><ArrowLeft /> {evidenceRef}</Link>} {...query} />
  )
}

const LETTER_KINDS: LetterKind[] = ['telecom_subscriber', 'telecom_imei', 'bank_kyc', 'cctv_preservation']

export function LetterPage() {
  const { reference: caseRef = '', kind = '' } = useParams()
  const [search] = useSearchParams()
  const valid = (LETTER_KINDS as string[]).includes(kind)
  const query = useLetter(caseRef, (valid ? kind : 'telecom_subscriber') as LetterKind, search.toString())
  if (!valid) return <EmptyState icon={FileWarning} title="Unknown letter" description="FALCON drafts subscriber, IMEI, bank and CCTV requests." />
  return <DocumentShell back={<Link to={`/investigations/${caseRef}`}><ArrowLeft /> {caseRef}</Link>} {...query} />
}

function DocumentShell({ back, data, isPending, isError, error, refetch, isFetching }: {
  back: ReactNode
  data: DraftDocument | undefined
  isPending: boolean
  isError: boolean
  error: unknown
  refetch: () => unknown
  isFetching: boolean
}) {
  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <div data-print="hide" className="flex flex-wrap items-center gap-2">
        <Button asChild variant="ghost" size="sm" className="-ml-2 text-muted-foreground">{back}</Button>
        {data && <Button size="sm" className="ml-auto" onClick={() => window.print()}><Printer /> Print / save as PDF</Button>}
      </div>
      {isPending ? (
        <Skeleton className="h-[640px] w-full" />
      ) : isError || !data ? (
        <ErrorState description={error instanceof ApiError ? error.message : 'The document could not be drafted.'} onRetry={() => refetch()} retrying={isFetching} />
      ) : (
        <DraftDocumentView doc={data} />
      )}
    </div>
  )
}
