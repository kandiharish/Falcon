import { MapPin, UserRound } from 'lucide-react'
import { Skeleton } from '@/components/ui/skeleton'
import { useInvestigationContext } from '@/app/investigation-context'
import { useInvestigation } from '@/services/queries'
import { PriorityBadge, StatusBadge } from '@/design-system/badges'
import { IdTag } from '@/design-system/IdTag'
import { WorkflowStepper } from '@/design-system/WorkflowStepper'

/**
 * Always-visible strip: CURRENT INVESTIGATION + where it is in the workflow (plan §7, §44).
 */
export function InvestigationContextBar() {
  const currentId = useInvestigationContext((s) => s.currentInvestigationId)
  const { data: investigation, isPending } = useInvestigation(currentId)

  if (!currentId) return null

  return (
    <div className="border-b bg-card/60 px-4 py-2 lg:px-6">
      {isPending || !investigation ? (
        <Skeleton className="h-6 w-full max-w-2xl" />
      ) : (
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
          <div className="flex min-w-0 items-center gap-2">
            <IdTag>{investigation.id}</IdTag>
            <span className="truncate text-sm font-medium">{investigation.title}</span>
            <StatusBadge kind="investigation" status={investigation.status} />
            <PriorityBadge priority={investigation.priority} />
          </div>
          <div className="hidden items-center gap-3 text-xs text-muted-foreground md:flex">
            <span className="flex items-center gap-1">
              <UserRound aria-hidden className="size-3.5" />
              {investigation.leadInvestigator}
            </span>
            <span className="flex items-center gap-1">
              <MapPin aria-hidden className="size-3.5" />
              {investigation.location}
            </span>
          </div>
          <WorkflowStepper
            stage={investigation.stage}
            className="ml-auto hidden overflow-x-auto 2xl:flex"
          />
        </div>
      )}
    </div>
  )
}
