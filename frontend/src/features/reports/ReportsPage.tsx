import { useState } from 'react'
import { Link, useNavigate } from 'react-router'
import { FileText, FolderSearch, Plus, ShieldCheck } from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Checkbox } from '@/components/ui/checkbox'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Skeleton } from '@/components/ui/skeleton'
import { Textarea } from '@/components/ui/textarea'
import { ApiError } from '@/services/apiClient'
import { can } from '@/services/authService'
import { useCurrentUser, useGenerateReport, useInvestigation, useReports } from '@/services/queries'
import { IdTag } from '@/design-system/IdTag'
import { PageHeader } from '@/design-system/PageHeader'
import { EmptyState, ErrorState } from '@/design-system/states'
import { formatDateTime } from '@/lib/format'
import { cn } from '@/lib/utils'
import { useCurrentCase } from '@/features/extraction/useCaseAccess'

/** Reports for the current investigation (plan §24). */
export function ReportsPage() {
  const caseRef = useCurrentCase()
  const { data: user } = useCurrentUser()
  const { data: investigation } = useInvestigation(caseRef)
  const { data: reports, isPending, isError, error, refetch, isFetching } = useReports(caseRef)
  const [creating, setCreating] = useState(false)
  const canGenerate = can(user, 'report:generate') && (investigation?.myRoleInCase != null || user?.role === 'supervisor')

  if (!caseRef) {
    return (
      <div className="mx-auto max-w-3xl pt-6">
        <EmptyState icon={FolderSearch} title="No investigation selected" description="Choose an investigation in the top bar."
          action={<Button asChild variant="outline"><Link to="/investigations">Open investigations</Link></Button>} />
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-5xl space-y-5">
      <PageHeader
        eyebrow={<IdTag>{caseRef}</IdTag>}
        title="Reports"
        description="A report freezes the investigation at one moment and keeps observed evidence apart from interpretation. Each one carries a fingerprint, so any later change to it can be detected."
        actions={canGenerate && <Button onClick={() => setCreating(true)}><Plus /> Generate report</Button>}
      />
      {isError ? (
        <ErrorState description={error instanceof ApiError ? error.message : 'Reports could not be loaded.'} onRetry={() => refetch()} retrying={isFetching} />
      ) : isPending ? (
        <Skeleton className="h-48 w-full" />
      ) : reports.length === 0 ? (
        <EmptyState icon={FileText} title="No reports yet" description="Generate a report to share the current state of the investigation." />
      ) : (
        <Card className="py-2">
          <CardContent>
            <ul className="divide-y">
              {reports.map((r) => (
                <li key={r.reference} className="flex flex-wrap items-center gap-x-3 gap-y-1 py-3">
                  <FileText aria-hidden className="size-4 text-muted-foreground" />
                  <Link to={`/investigations/${caseRef}/reports/${r.reference}`} className="font-mono text-sm font-medium text-primary hover:underline">{r.reference}</Link>
                  <span className="min-w-0 flex-1 truncate text-sm font-medium">{r.title}</span>
                  <span className={cn('text-xs', r.status === 'failed' ? 'text-destructive' : 'text-muted-foreground')}>
                    {r.status === 'ready' ? `by ${r.generatedBy}, ${formatDateTime(r.createdAt)}` : r.status === 'failed' ? `Failed: ${r.errorMessage}` : 'Generating…'}
                  </span>
                  {r.sha256 && (
                    <span className="inline-flex items-center gap-1 font-mono text-[0.7rem] text-muted-foreground" title={`SHA-256 ${r.sha256}`}>
                      <ShieldCheck aria-hidden className="size-3.5" />{r.sha256.slice(0, 12)}…
                    </span>
                  )}
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}
      {creating && <GenerateDialog caseRef={caseRef} onClose={() => setCreating(false)} />}
    </div>
  )
}

function GenerateDialog({ caseRef, onClose }: { caseRef: string; onClose: () => void }) {
  const generate = useGenerateReport(caseRef)
  const navigate = useNavigate()
  const [title, setTitle] = useState(defaultTitle)
  const [notes, setNotes] = useState('')
  const [limitations, setLimitations] = useState('')
  const [includePending, setIncludePending] = useState(true)
  const submit = (event: React.FormEvent) => {
    event.preventDefault()
    generate.mutate(
      { title: title.trim(), analyst_notes: notes, limitations, include_pending: includePending },
      {
        onSuccess: (report) => {
          toast.success(`${report.reference} generated`)
          navigate(`/investigations/${caseRef}/reports/${report.reference}`)
        },
        onError: (err) => toast.error('The report could not be generated', { description: err instanceof ApiError ? err.message : undefined }),
      },
    )
  }
  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Generate report</DialogTitle>
          <DialogDescription>Takes a snapshot of {caseRef} as it is now. Your notes appear under "Analytical interpretation"; FALCON adds the limitations it finds itself.</DialogDescription>
        </DialogHeader>
        <form id="report-form" onSubmit={submit} className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="report-title">Title</Label>
            <Input id="report-title" value={title} onChange={(e) => setTitle(e.target.value)} minLength={3} maxLength={200} required />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="report-notes">Analyst notes</Label>
            <Textarea id="report-notes" value={notes} onChange={(e) => setNotes(e.target.value)} rows={4} maxLength={10000}
              placeholder="Your interpretation: what the evidence suggests, and what remains open." />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="report-limits">Known limitations</Label>
            <Textarea id="report-limits" value={limitations} onChange={(e) => setLimitations(e.target.value)} rows={2} maxLength={5000}
              placeholder="e.g. Subscriber details for the phone numbers have not been received yet." />
          </div>
          <label className="flex items-start gap-2 text-sm">
            <Checkbox checked={includePending} onCheckedChange={(v) => setIncludePending(v === true)} className="mt-0.5" />
            <span>Include items still awaiting review <span className="block text-xs text-muted-foreground">They are marked "requires review". Untick for a report of confirmed findings only.</span></span>
          </label>
        </form>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Cancel</Button>
          <Button type="submit" form="report-form" disabled={generate.isPending || title.trim().length < 3}>{generate.isPending ? 'Generating…' : 'Generate'}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

/** Read once, when the dialog opens. */
const defaultTitle = () => `Investigation report ${new Date().toISOString().slice(0, 10)}`
