import { ArrowRight, History } from 'lucide-react'
import { Card, CardContent } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import type { AuditEntry, InvestigationStatus, Priority } from '@/domain/types'
import { useInvestigationActivity } from '@/services/queries'
import { EmptyState, ErrorState } from '@/design-system/states'
import {
  auditActionLabels,
  fieldLabels,
  investigationStatusTerms,
  priorityTerms,
  workflowStages,
} from '@/design-system/vocabulary'
import { formatDateTime } from '@/lib/format'

/** Investigation activity (plan §10, §25): the audit trail of this case, newest first. */
export function ActivityTab({ reference }: { reference: string }) {
  const { data: entries, isPending, isError, refetch, isFetching } = useInvestigationActivity(reference)

  if (isPending) return <Skeleton className="h-40 w-full" />
  if (isError) {
    return <ErrorState description="Activity could not be loaded." onRetry={() => refetch()} retrying={isFetching} />
  }
  if (entries.length === 0) {
    return <EmptyState icon={History} title="No activity yet" description="Changes to this investigation will appear here." />
  }

  return (
    <Card>
      <CardContent>
        <ol className="relative space-y-5 border-l pl-5">
          {entries.map((entry) => (
            <li key={entry.id} className="relative">
              <span aria-hidden className="absolute top-1.5 -left-[1.4rem] size-2.5 rounded-full border-2 border-background bg-primary" />
              <p className="text-sm">
                <span className="font-medium">{entry.actorEmail ?? 'System'}</span>{' '}
                <span className="text-muted-foreground">
                  {(auditActionLabels[entry.action] ?? entry.action).toLowerCase()}
                </span>
              </p>
              <p className="text-xs text-muted-foreground tabular-nums">{formatDateTime(entry.occurredAt)}</p>
              <Changes entry={entry} />
            </li>
          ))}
        </ol>
      </CardContent>
    </Card>
  )
}

/** "Priority: Medium → Critical" for every field that changed. */
function Changes({ entry }: { entry: AuditEntry }) {
  if (entry.action !== 'investigation.updated' && entry.action !== 'investigation.member_added') return null
  const fields = Object.keys(entry.newState ?? {})
  if (fields.length === 0) return null
  return (
    <ul className="mt-1.5 space-y-1 rounded-md bg-muted/50 px-3 py-2 text-xs">
      {fields.map((field) => (
        <li key={field} className="flex flex-wrap items-center gap-1.5">
          <span className="text-muted-foreground">{fieldLabels[field] ?? field}:</span>
          {entry.previousState && field in entry.previousState && (
            <>
              <span className="line-through decoration-muted-foreground/60">
                {display(field, entry.previousState[field])}
              </span>
              <ArrowRight aria-label="changed to" className="size-3 text-muted-foreground" />
            </>
          )}
          <span className="font-medium">{display(field, entry.newState?.[field])}</span>
        </li>
      ))}
    </ul>
  )
}

function display(field: string, value: unknown): string {
  if (value === null || value === undefined || value === '') return '—'
  if (field === 'status') return investigationStatusTerms[value as InvestigationStatus]?.label ?? String(value)
  if (field === 'priority') return priorityTerms[value as Priority]?.label ?? String(value)
  if (field === 'stage') return workflowStages.find((s) => s.stage === value)?.label ?? String(value)
  if (Array.isArray(value)) return value.join(', ')
  return String(value)
}
