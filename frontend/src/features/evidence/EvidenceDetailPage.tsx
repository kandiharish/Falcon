import { Link, useParams } from 'react-router'
import {
  ArrowLeft,
  BadgeCheck,
  CircleAlert,
  Download,
  FileQuestion,
  Fingerprint,
  History,
  RefreshCw,
  ShieldAlert,
  ShieldCheck,
} from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import type { Evidence } from '@/domain/types'
import { ApiError } from '@/services/apiClient'
import { can } from '@/services/authService'
import { EvidenceService, isProcessing } from '@/services/evidenceService'
import {
  useCurrentUser,
  useEvidence,
  useEvidenceAction,
  useEvidenceHistory,
  useInvestigation,
} from '@/services/queries'
import { AssertionLabel, StatusBadge } from '@/design-system/badges'
import { IdTag } from '@/design-system/IdTag'
import { PageHeader } from '@/design-system/PageHeader'
import { ProcessingProgress } from '@/design-system/ProcessingProgress'
import { EmptyState, ErrorState } from '@/design-system/states'
import { auditActionLabels, evidenceTypeTerms } from '@/design-system/vocabulary'
import { formatBytes, formatDateTime } from '@/lib/format'

/** Evidence detail workspace (plan §12). */
export function EvidenceDetailPage() {
  const { reference: caseRef = '', evidenceRef = '' } = useParams()
  const { data: evidence, isPending, isError, error, refetch, isFetching } = useEvidence(caseRef, evidenceRef)

  if (isPending) {
    return (
      <div className="mx-auto max-w-7xl space-y-4">
        <Skeleton className="h-6 w-48" />
        <Skeleton className="h-8 w-1/2" />
        <Skeleton className="h-72 w-full" />
      </div>
    )
  }
  if (isError) {
    const notFound = error instanceof ApiError && error.status === 404
    return (
      <div className="mx-auto max-w-3xl pt-6">
        {notFound ? (
          <EmptyState
            icon={FileQuestion}
            title="Evidence not found"
            description={error.message}
            action={<Button asChild variant="outline"><Link to="/evidence">Back to evidence</Link></Button>}
          />
        ) : (
          <ErrorState
            description={error instanceof ApiError ? error.message : 'The evidence could not be loaded.'}
            onRetry={() => refetch()}
            retrying={isFetching}
          />
        )}
      </div>
    )
  }

  const term = evidenceTypeTerms[evidence.evidenceType]
  return (
    <div className="mx-auto max-w-7xl space-y-6">
      <Button asChild variant="ghost" size="sm" className="-ml-2 text-muted-foreground">
        <Link to="/evidence"><ArrowLeft /> Evidence</Link>
      </Button>

      <PageHeader
        eyebrow={
          <span className="flex flex-wrap items-center gap-2">
            <IdTag>{evidence.reference}</IdTag>
            <span className="inline-flex items-center gap-1">
              <term.icon aria-hidden className="size-3.5" /> {term.label}
            </span>
            <StatusBadge kind="evidence" status={evidence.status} />
            <Link to={`/investigations/${caseRef}`} className="hover:underline">
              <IdTag>{caseRef}</IdTag>
            </Link>
          </span>
        }
        title={evidence.description || evidence.source || evidence.originalFilename}
        description={
          evidence.collectedAt
            ? `Collected ${formatDateTime(evidence.collectedAt)}${evidence.locationText ? ` · ${evidence.locationText}` : ''}`
            : evidence.locationText || undefined
        }
        actions={<Actions evidence={evidence} caseRef={caseRef} />}
      />

      {isProcessing(evidence) && evidence.latestJob && (
        <Card>
          <CardContent>
            <ProcessingProgress
              percent={evidence.latestJob.progress}
              currentStep={evidence.latestJob.currentStep ?? 'Waiting in queue'}
            />
          </CardContent>
        </Card>
      )}

      <Tabs defaultValue="overview">
        <TabsList className="flex-wrap">
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="preview">Preview</TabsTrigger>
          <TabsTrigger value="metadata">Metadata</TabsTrigger>
          <TabsTrigger value="processing">Processing</TabsTrigger>
          <TabsTrigger value="integrity">Integrity</TabsTrigger>
          <TabsTrigger value="history">History</TabsTrigger>
        </TabsList>
        <TabsContent value="overview" className="pt-4"><OverviewTab evidence={evidence} caseRef={caseRef} /></TabsContent>
        <TabsContent value="preview" className="pt-4"><PreviewTab evidence={evidence} caseRef={caseRef} /></TabsContent>
        <TabsContent value="metadata" className="pt-4"><MetadataTab evidence={evidence} /></TabsContent>
        <TabsContent value="processing" className="pt-4"><ProcessingTab evidence={evidence} /></TabsContent>
        <TabsContent value="integrity" className="pt-4"><IntegrityTab evidence={evidence} caseRef={caseRef} /></TabsContent>
        <TabsContent value="history" className="pt-4"><HistoryTab caseRef={caseRef} evidenceRef={evidence.reference} /></TabsContent>
      </Tabs>
    </div>
  )
}

function Actions({ evidence, caseRef }: { evidence: Evidence; caseRef: string }) {
  const { data: user } = useCurrentUser()
  const { data: investigation } = useInvestigation(caseRef)
  const action = useEvidenceAction(caseRef, evidence.reference)
  const onTeam = investigation?.myRoleInCase != null || user?.role === 'supervisor'
  const canReview = can(user, 'evidence:verify') && onTeam
  const failed = evidence.latestJob?.status === 'failed'

  const run = (kind: Parameters<typeof action.mutate>[0], success: string) =>
    action.mutate(kind, {
      onSuccess: () => toast.success(success),
      onError: (err) => toast.error('Action failed', { description: err instanceof ApiError ? err.message : undefined }),
    })

  return (
    <div className="flex flex-wrap gap-2">
      <Button asChild variant="outline">
        {/* A real link: the browser downloads the original; the server records it in the audit log */}
        <a href={EvidenceService.contentUrl(caseRef, evidence.reference)}>
          <Download /> Original
        </a>
      </Button>
      {failed && can(user, 'evidence:upload') && onTeam && (
        <Button variant="outline" disabled={action.isPending} onClick={() => run({ kind: 'reprocess' }, 'Processing restarted')}>
          <RefreshCw /> Reprocess
        </Button>
      )}
      {canReview && ['processed', 'requires_review'].includes(evidence.status) && (
        <Button
          disabled={action.isPending || evidence.integrityOk === false}
          onClick={() => run({ kind: 'status', status: 'verified' }, `${evidence.reference} marked as verified`)}
        >
          <BadgeCheck /> Mark verified
        </Button>
      )}
      {canReview && evidence.status === 'verified' && (
        <Button
          variant="outline"
          disabled={action.isPending}
          onClick={() => run({ kind: 'status', status: 'requires_review' }, 'Sent back for review')}
        >
          <CircleAlert /> Needs review
        </Button>
      )}
    </div>
  )
}

function Detail({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1">
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="break-words">{children}</dd>
    </div>
  )
}

/** Was this value typed by a person, or read from inside the file? (plan §13, §22) */
function Provenance({ evidence, field }: { evidence: Evidence; field: string }) {
  const image = evidence.fileMetadata.image as { provenance?: Record<string, string> } | undefined
  const source = image?.provenance?.[field]
  return <AssertionLabel kind={source ? 'extracted' : 'user_entered'} className="ml-1.5 align-middle" />
}

function OverviewTab({ evidence, caseRef }: { evidence: Evidence; caseRef: string }) {
  return (
    <div className="grid gap-6 lg:grid-cols-3">
      <Card className="lg:col-span-2">
        <CardHeader><CardTitle>Evidence details</CardTitle></CardHeader>
        <CardContent>
          <dl className="grid grid-cols-1 gap-x-6 gap-y-4 text-sm sm:grid-cols-2">
            <Detail label="Source">{evidence.source || '—'}</Detail>
            <Detail label="Original file">
              <span className="font-mono text-xs">{evidence.originalFilename}</span>
            </Detail>
            <Detail label="Collected at">
              {evidence.collectedAt ? (
                <>
                  {formatDateTime(evidence.collectedAt)}
                  <Provenance evidence={evidence} field="collected_at" />
                </>
              ) : '—'}
            </Detail>
            <Detail label="Location">
              {evidence.locationText || '—'}
              {evidence.latitude !== null && (
                <span className="block font-mono text-xs text-muted-foreground">
                  {evidence.latitude.toFixed(5)}, {evidence.longitude?.toFixed(5)}
                  <Provenance evidence={evidence} field="latitude" />
                </span>
              )}
            </Detail>
            <Detail label="Uploaded by">{evidence.uploadedBy} · {formatDateTime(evidence.createdAt)}</Detail>
            <Detail label="Tags">{evidence.tags.length ? evidence.tags.join(', ') : '—'}</Detail>
            <div className="sm:col-span-2">
              <Detail label="Description">{evidence.description || '—'}</Detail>
            </div>
          </dl>
        </CardContent>
      </Card>
      <Card>
        <CardHeader><CardTitle>Preview</CardTitle></CardHeader>
        <CardContent>
          {evidence.hasPreview ? (
            <img
              src={EvidenceService.previewUrl(caseRef, evidence.reference)}
              alt={`Preview of ${evidence.reference}`}
              className="w-full rounded-md border"
            />
          ) : (
            <p className="text-sm text-muted-foreground">No visual preview for this type of file. See the Preview tab.</p>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

function PreviewTab({ evidence, caseRef }: { evidence: Evidence; caseRef: string }) {
  const text = evidence.fileMetadata.text as
    | { text_preview?: string; columns?: string[]; sample_rows?: string[][]; row_count?: number }
    | undefined

  if (evidence.hasPreview) {
    return (
      <Card>
        <CardContent>
          <img
            src={EvidenceService.previewUrl(caseRef, evidence.reference)}
            alt={`Preview of ${evidence.reference}`}
            className="mx-auto max-h-[70svh] rounded-md border"
          />
          <p className="mt-2 text-center text-xs text-muted-foreground">
            Reduced copy for viewing. The original is unchanged — use “Original” to download it.
          </p>
        </CardContent>
      </Card>
    )
  }
  if (text?.columns) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>First rows</CardTitle>
          <CardDescription>{text.row_count} data rows in total</CardDescription>
        </CardHeader>
        <CardContent className="overflow-x-auto">
          <table className="w-full text-left font-mono text-xs">
            <thead>
              <tr>{text.columns.map((c) => <th key={c} className="border-b px-2 py-1.5 font-medium">{c}</th>)}</tr>
            </thead>
            <tbody>
              {text.sample_rows?.map((row, i) => (
                <tr key={i} className="border-b last:border-0">
                  {row.map((cell, j) => <td key={j} className="px-2 py-1.5 whitespace-nowrap">{cell}</td>)}
                </tr>
              ))}
            </tbody>
          </table>
        </CardContent>
      </Card>
    )
  }
  if (text?.text_preview) {
    return (
      <Card>
        <CardContent>
          <pre className="max-h-[60svh] overflow-auto rounded-md bg-muted p-3 font-mono text-xs whitespace-pre-wrap">{text.text_preview}</pre>
        </CardContent>
      </Card>
    )
  }
  return (
    <EmptyState
      icon={FileQuestion}
      title="No preview available"
      description={isProcessing(evidence) ? 'The preview appears when processing finishes.' : 'Previews for this kind of file arrive in Phase 6 (documents, video).'}
    />
  )
}

function MetadataTab({ evidence }: { evidence: Evidence }) {
  const rows: [string, string][] = [
    ['Media type (detected from content)', evidence.mediaType],
    ['Size', `${formatBytes(evidence.sizeBytes)} (${evidence.sizeBytes.toLocaleString()} bytes)`],
  ]
  const image = evidence.fileMetadata.image as Record<string, unknown> | undefined
  if (image) {
    rows.push(['Dimensions', `${image.width} × ${image.height} px`], ['Image format', String(image.format)])
    for (const [key, value] of Object.entries((image.exif as Record<string, string>) ?? {})) {
      rows.push([`EXIF ${key}`, value])
    }
  }
  const text = evidence.fileMetadata.text as Record<string, unknown> | undefined
  if (text?.columns) rows.push(['Columns', (text.columns as string[]).join(', ')], ['Data rows', String(text.row_count)])

  return (
    <Card>
      <CardHeader>
        <CardTitle>Technical metadata</CardTitle>
        <CardDescription>
          <AssertionLabel kind="extracted" /> Read automatically from the file during processing.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <dl className="divide-y text-sm">
          {rows.map(([label, value]) => (
            <div key={label} className="grid grid-cols-1 gap-1 py-2 sm:grid-cols-3">
              <dt className="text-muted-foreground">{label}</dt>
              <dd className="font-mono text-xs break-all sm:col-span-2">{value}</dd>
            </div>
          ))}
        </dl>
      </CardContent>
    </Card>
  )
}

function ProcessingTab({ evidence }: { evidence: Evidence }) {
  const job = evidence.latestJob
  if (!job) return <EmptyState icon={History} title="Not processed yet" description="Processing has not been started." />
  return (
    <Card>
      <CardHeader>
        <CardTitle>Processing pipeline</CardTitle>
        <CardDescription>
          Attempt {job.attempts} · {job.status === 'succeeded' ? 'Completed' : job.status === 'failed' ? 'Failed' : 'In progress'}
          {job.finishedAt && ` · ${formatDateTime(job.finishedAt)}`}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {job.errorMessage && (
          <div role="alert" className="flex gap-2 rounded-md border border-warning/30 bg-warning/10 p-3 text-sm">
            <CircleAlert aria-hidden className="mt-0.5 size-4 shrink-0 text-warning" />
            {job.errorMessage}
          </div>
        )}
        <ol className="space-y-3">
          {job.steps.map((step, index) => (
            <li key={step.name} className="flex gap-3">
              <span className="flex size-6 shrink-0 items-center justify-center rounded-full bg-muted font-mono text-xs">{index + 1}</span>
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium">
                  {step.label}{' '}
                  <span className={step.status === 'done' ? 'text-success' : 'text-destructive'}>
                    · {step.status === 'done' ? 'done' : 'failed'}
                  </span>
                  <span className="ml-2 font-mono text-xs text-muted-foreground">{step.durationMs} ms</span>
                </p>
                <p className="text-sm text-muted-foreground">{step.summary}</p>
              </div>
            </li>
          ))}
        </ol>
      </CardContent>
    </Card>
  )
}

function IntegrityTab({ evidence, caseRef }: { evidence: Evidence; caseRef: string }) {
  const action = useEvidenceAction(caseRef, evidence.reference)
  const ok = evidence.integrityOk
  return (
    <Card>
      <CardHeader>
        <CardTitle>Evidence integrity</CardTitle>
        <CardDescription>
          The SHA-256 fingerprint was computed when the file arrived. Re-checking reads the stored
          original again and compares the two.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex items-start gap-3 rounded-md border p-3">
          {ok === false ? (
            <ShieldAlert aria-hidden className="size-5 shrink-0 text-destructive" />
          ) : ok ? (
            <ShieldCheck aria-hidden className="size-5 shrink-0 text-success" />
          ) : (
            <Fingerprint aria-hidden className="size-5 shrink-0 text-muted-foreground" />
          )}
          <div className="text-sm">
            <p className="font-medium">
              {ok === false ? 'Fingerprint MISMATCH — the stored file differs from the upload' : ok ? 'Fingerprint matches' : 'Not checked yet'}
            </p>
            <p className="text-muted-foreground">
              {evidence.integrityCheckedAt ? `Last checked ${formatDateTime(evidence.integrityCheckedAt)}` : 'Run a check to confirm the original is unchanged.'}
            </p>
          </div>
        </div>
        <dl className="grid gap-3 text-sm">
          <Detail label="SHA-256 fingerprint"><code className="font-mono text-xs break-all">{evidence.sha256}</code></Detail>
          <Detail label="Size">{evidence.sizeBytes.toLocaleString()} bytes</Detail>
          <Detail label="Uploaded">{evidence.uploadedBy} · {formatDateTime(evidence.createdAt)}</Detail>
        </dl>
        <Button
          variant="outline"
          disabled={action.isPending}
          onClick={() =>
            action.mutate({ kind: 'verify-integrity' }, {
              onSuccess: (e) => (e.integrityOk ? toast.success('Integrity confirmed: fingerprint matches') : toast.error('Integrity check FAILED')),
            })
          }
        >
          <Fingerprint /> {action.isPending ? 'Checking…' : 'Check integrity now'}
        </Button>
      </CardContent>
    </Card>
  )
}

function HistoryTab({ caseRef, evidenceRef }: { caseRef: string; evidenceRef: string }) {
  const { data: entries, isPending, isError, refetch } = useEvidenceHistory(caseRef, evidenceRef)
  if (isPending) return <Skeleton className="h-40 w-full" />
  if (isError) return <ErrorState description="History could not be loaded." onRetry={() => refetch()} />
  return (
    <Card>
      <CardHeader>
        <CardTitle>Audit trail</CardTitle>
        <CardDescription>Every access and change to this evidence item. Entries cannot be edited.</CardDescription>
      </CardHeader>
      <CardContent>
        <ol className="space-y-3">
          {entries.map((entry) => (
            <li key={entry.id} className="flex flex-wrap items-baseline justify-between gap-2 border-b pb-2 text-sm last:border-0">
              <span>
                <span className="font-medium">{auditActionLabels[entry.action] ?? entry.action}</span>
                <span className="text-muted-foreground"> · {entry.actorEmail ?? 'system'}</span>
                {entry.note && <span className="block text-xs text-muted-foreground">{entry.note}</span>}
              </span>
              <span className="text-xs text-muted-foreground tabular-nums">{formatDateTime(entry.occurredAt)}</span>
            </li>
          ))}
        </ol>
      </CardContent>
    </Card>
  )
}
