import { Link, useParams } from 'react-router'
import { ArrowLeft, Download, FileText, Printer, ShieldAlert, ShieldCheck } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { ApiError } from '@/services/apiClient'
import { ReportService } from '@/services/reportService'
import { useReport } from '@/services/queries'
import { EmptyState, ErrorState } from '@/design-system/states'
import { ReportDocument } from './ReportDocument'

/** Report preview with print and export (plan §24). Printing hides the app around it. */
export function ReportDetailPage() {
  const { reference: caseRef = '', reportRef = '' } = useParams()
  const { data: report, isPending, isError, error, refetch, isFetching } = useReport(caseRef, reportRef)

  if (isPending) return <div className="mx-auto max-w-4xl space-y-4"><Skeleton className="h-8 w-1/3" /><Skeleton className="h-96 w-full" /></div>
  if (isError) {
    return (
      <div className="mx-auto max-w-3xl pt-6">
        {error instanceof ApiError && error.status === 404 ? (
          <EmptyState icon={FileText} title="Report not found" description={error.message}
            action={<Button asChild variant="outline"><Link to="/reports">Back to reports</Link></Button>} />
        ) : (
          <ErrorState description="The report could not be loaded." onRetry={() => refetch()} retrying={isFetching} />
        )}
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-4xl space-y-4">
      <div data-print="hide" className="flex flex-wrap items-center gap-2">
        <Button asChild variant="ghost" size="sm" className="-ml-2 text-muted-foreground">
          <Link to="/reports"><ArrowLeft /> Reports</Link>
        </Button>
        <span className={report.intact ? 'inline-flex items-center gap-1 text-xs text-success' : 'inline-flex items-center gap-1 text-xs font-semibold text-destructive'}>
          {report.intact ? <ShieldCheck aria-hidden className="size-4" /> : <ShieldAlert aria-hidden className="size-4" />}
          {report.intact ? 'Fingerprint matches: unaltered since generation' : 'Fingerprint MISMATCH: this report may have been altered'}
        </span>
        <div className="ml-auto flex gap-2">
          <Button variant="outline" size="sm" asChild>
            <a href={ReportService.exportUrl(caseRef, report.reference)} download><Download /> Download JSON</a>
          </Button>
          <Button size="sm" onClick={() => window.print()}><Printer /> Print / save as PDF</Button>
        </div>
      </div>
      {report.status !== 'ready' || !report.content ? (
        <ErrorState description={report.errorMessage ?? 'This report is not ready.'} />
      ) : (
        <ReportDocument content={report.content} sha256={report.sha256} intact={report.intact} />
      )}
    </div>
  )
}
