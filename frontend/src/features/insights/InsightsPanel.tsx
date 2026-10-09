/**
 * "FALCON suggests": what the case data says to check next (clock drift, gaps, unknown
 * owners, other cases, waiting leads). Each one shows its reasons and the records behind it,
 * and offers the next step — open the records, or draft the request that would fill the gap.
 */
import { Link } from 'react-router'
import { ArrowRight, Clock3, FileText, FolderSymlink, Lightbulb, Route, ScanSearch, UserRoundSearch, type LucideIcon } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { letterParams, type Insight, type LetterRequest } from '@/services/documentsService'
import { useInsights } from '@/services/queries'
import { IdTag } from '@/design-system/IdTag'
import { EmptyState, ErrorState } from '@/design-system/states'
import { cn } from '@/lib/utils'

const KIND: Record<Insight['kind'], { icon: LucideIcon; label: string }> = {
  other_case: { icon: FolderSymlink, label: 'Other case' },
  clock_drift: { icon: Clock3, label: 'Clock' },
  waiting_lead: { icon: ScanSearch, label: 'Waiting lead' },
  sighting_gap: { icon: Route, label: 'Gap' },
  unknown_owner: { icon: UserRoundSearch, label: 'Who is this?' },
}

const LETTER_LABEL: Record<string, string> = {
  telecom_subscriber: 'Draft operator request',
  telecom_imei: 'Draft IMEI request',
  bank_kyc: 'Draft bank request',
  cctv_preservation: 'Draft CCTV request',
}

export function InsightsPanel({ caseRef, limit }: { caseRef: string; limit?: number }) {
  const { data, isPending, isError, refetch, isFetching } = useInsights(caseRef)
  if (isPending) return <div className="space-y-2">{[0, 1, 2].map((i) => <Skeleton key={i} className="h-20 w-full" />)}</div>
  if (isError) return <ErrorState description="Suggestions could not be worked out." onRetry={() => refetch()} retrying={isFetching} />
  if (data.items.length === 0)
    return <EmptyState icon={Lightbulb} title="Nothing to suggest" description="FALCON has no open questions about this case's records." />
  const shown = limit ? data.items.slice(0, limit) : data.items
  return (
    <div className="space-y-3">
      <ul className="space-y-2">
        {shown.map((insight) => <InsightRow key={insight.key} caseRef={caseRef} insight={insight} />)}
      </ul>
      <p className="text-xs text-muted-foreground">
        {data.note}{limit && data.items.length > limit ? ` ${data.items.length - limit} more on the case page.` : ''}
      </p>
    </div>
  )
}

function InsightRow({ caseRef, insight }: { caseRef: string; insight: Insight }) {
  const { icon: Icon, label } = KIND[insight.kind]
  const letter = insight.letter as LetterRequest | null
  const lead = insight.kind === 'waiting_lead' ? insight.key.split(':')[1] : null
  const otherCase = insight.kind === 'other_case' ? insight.key.split(':')[2] : null
  return (
    <li className={cn('rounded-lg border-l-4 bg-muted/30 p-3', insight.severity === 'high' ? 'border-l-warning' : 'border-l-info')}>
      <div className="flex items-start gap-2.5">
        <Icon aria-hidden className={cn('mt-0.5 size-4 shrink-0', insight.severity === 'high' ? 'text-warning' : 'text-info')} />
        <div className="min-w-0 flex-1 space-y-1.5">
          <p className="text-sm font-medium">
            <span className="sr-only">{insight.severity === 'high' ? 'Important. ' : ''}{label}: </span>
            {insight.title}
          </p>
          <p className="text-sm text-muted-foreground">{insight.detail}</p>
          <p className="text-sm"><span className="font-medium">Next: </span>{insight.action}</p>
          <div className="flex flex-wrap items-center gap-1.5 pt-0.5">
            {insight.evidence.map((ref) => (
              <Link key={ref} to={`/investigations/${caseRef}/evidence/${ref}`} className="rounded outline-none focus-visible:ring-2 focus-visible:ring-ring">
                <IdTag>{ref}</IdTag>
              </Link>
            ))}
            {insight.entities.map((ref) => (
              <Link key={ref} to={`/investigations/${caseRef}/entities/${ref}`} className="rounded outline-none focus-visible:ring-2 focus-visible:ring-ring">
                <IdTag>{ref}</IdTag>
              </Link>
            ))}
            <span className="ml-auto flex flex-wrap gap-1.5">
              {lead && <Button asChild size="xs" variant="outline"><Link to={`/investigations/${caseRef}/correlations/${lead}`}>Review {lead} <ArrowRight /></Link></Button>}
              {otherCase && otherCase !== 'restricted' && <Button asChild size="xs" variant="outline"><Link to={`/investigations/${otherCase}`}>Open {otherCase} <ArrowRight /></Link></Button>}
              {letter && (
                <Button asChild size="xs" variant="outline">
                  <Link to={`/investigations/${caseRef}/letters/${letter.kind}?${letterParams(letter)}`}><FileText /> {LETTER_LABEL[letter.kind]}</Link>
                </Button>
              )}
            </span>
          </div>
        </div>
      </div>
    </li>
  )
}
