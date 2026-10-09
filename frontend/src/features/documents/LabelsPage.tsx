/**
 * Printable evidence labels for the property room (malkhana): the evidence ID, what it is,
 * its SHA-256 fingerprint and a QR code. Scanning the code opens the evidence in FALCON and
 * re-checks the stored file against its fingerprint, so a sealed packet can be matched to
 * its record in seconds.
 */
import { useEffect, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router'
import QRCode from 'qrcode'
import { ArrowLeft, Printer, Tags } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import type { Evidence } from '@/domain/types'
import { useEvidenceList, useInvestigation } from '@/services/queries'
import { evidenceTypeTerms } from '@/design-system/vocabulary'
import { EmptyState, ErrorState } from '@/design-system/states'
import { formatInZone } from '@/lib/time'

export function LabelsPage() {
  const { reference: caseRef = '' } = useParams()
  const [search] = useSearchParams()
  const only = search.get('evidence')
  const { data: investigation } = useInvestigation(caseRef)
  const { data, isPending, isError, refetch, isFetching } = useEvidenceList(caseRef, { limit: 100 })
  const items = (data?.items ?? []).filter((e) => !only || e.reference === only).sort((a, b) => a.reference.localeCompare(b.reference))

  return (
    <div className="mx-auto max-w-5xl space-y-4">
      <div data-print="hide" className="flex flex-wrap items-center gap-2">
        <Button asChild variant="ghost" size="sm" className="-ml-2 text-muted-foreground">
          <Link to={only ? `/investigations/${caseRef}/evidence/${only}` : `/investigations/${caseRef}`}><ArrowLeft /> {only ?? caseRef}</Link>
        </Button>
        <p className="text-sm text-muted-foreground">
          Stick one on each sealed packet. Scanning the code opens the record and re-checks the file.
        </p>
        {items.length > 0 && <Button size="sm" className="ml-auto" onClick={() => window.print()}><Printer /> Print labels</Button>}
      </div>
      {isError ? (
        <ErrorState description="The evidence list could not be loaded." onRetry={() => refetch()} retrying={isFetching} />
      ) : isPending ? (
        <Skeleton className="h-64 w-full" />
      ) : items.length === 0 ? (
        <EmptyState icon={Tags} title="No evidence to label" description="Labels appear once evidence is added." />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 print:grid-cols-2 print:gap-2">
          {items.map((e) => <Label key={e.reference} evidence={e} caseTitle={investigation?.title ?? ''} timeZone={investigation?.timeZone ?? 'UTC'} />)}
        </div>
      )}
    </div>
  )
}

function Label({ evidence, caseTitle, timeZone }: { evidence: Evidence; caseTitle: string; timeZone: string }) {
  const [qr, setQr] = useState<string | null>(null)
  const url = `${window.location.origin}/investigations/${evidence.investigationReference}/evidence/${evidence.reference}?verify=1`

  useEffect(() => {
    let alive = true
    QRCode.toString(url, { type: 'svg', margin: 0, errorCorrectionLevel: 'M' }).then((svg) => alive && setQr(svg))
    return () => {
      alive = false
    }
  }, [url])

  return (
    <article className="flex break-inside-avoid gap-4 rounded-md border-2 border-dashed border-neutral-400 bg-white p-4 text-neutral-900">
      <div className="size-28 shrink-0" role="img" aria-label={`QR code linking to ${evidence.reference}`}
        // The SVG is generated locally from our own URL (no user HTML is inserted).
        dangerouslySetInnerHTML={qr ? { __html: qr } : undefined} />
      <div className="min-w-0 space-y-1 text-xs">
        <p className="font-semibold tracking-[0.2em] text-neutral-500">FALCON · EVIDENCE</p>
        <p className="font-mono text-xl font-bold">{evidence.reference}</p>
        <p className="font-mono">{evidence.investigationReference} · {evidenceTypeTerms[evidence.evidenceType]?.label}</p>
        <p className="line-clamp-2">{evidence.description || caseTitle}</p>
        {evidence.collectedAt && <p>Collected {formatInZone(evidence.collectedAt, timeZone)}</p>}
        <p className="font-mono text-[0.65rem] break-all text-neutral-600" title={evidence.sha256}>
          SHA-256 {evidence.sha256.slice(0, 16)}…{evidence.sha256.slice(-8)}
        </p>
      </div>
    </article>
  )
}
