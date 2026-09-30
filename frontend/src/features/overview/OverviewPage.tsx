import { ArrowRight, FolderSearch, Info } from 'lucide-react'
import { Link } from 'react-router'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { useInvestigationContext } from '@/app/investigation-context'
import { useInvestigation, useInvestigations } from '@/services/queries'
import type { WorkflowStage } from '@/domain/types'
import { PriorityBadge, StatusBadge } from '@/design-system/badges'
import { IdTag } from '@/design-system/IdTag'
import { PageHeader } from '@/design-system/PageHeader'
import { EmptyState, ErrorState } from '@/design-system/states'
import { WorkflowStepper } from '@/design-system/WorkflowStepper'
import { formatDateTime } from '@/lib/format'
import { cn } from '@/lib/utils'
import { SystemStatusCard } from './SystemStatusCard'

const nextStepByStage: Record<WorkflowStage, string> = {
  intake: 'Add and validate evidence for this investigation.',
  processing: 'Evidence is being processed. Review items that fail validation.',
  extraction: 'Review extracted entities and events before correlation.',
  correlation: 'Review potential relationships detected across evidence sources.',
  review: 'Supervisor review of findings and analyst notes.',
  reporting: 'Generate and verify the investigation report.',
  closed: 'Investigation closed. Records are read-only.',
}

export function OverviewPage() {
  const currentId = useInvestigationContext((s) => s.currentInvestigationId)

  return (
    <div className="mx-auto max-w-7xl space-y-6">
      <PageHeader
        title="Investigation overview"
        description="Understand the state of the current investigation within seconds."
      />

      <div className="flex items-start gap-2 rounded-lg border border-info/25 bg-info/5 px-3 py-2 text-sm">
        <Info aria-hidden className="mt-0.5 size-4 shrink-0 text-info" />
        <p className="text-muted-foreground">
          Evidence, entity, event and correlation metrics appear here once evidence management is
          built (Phase 4–5). All case data shown is fictional demonstration data.
        </p>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <CurrentInvestigationCard id={currentId} className="lg:col-span-2" />
        <SystemStatusCard />
      </div>

      <InvestigationsTable />
    </div>
  )
}

function CurrentInvestigationCard({ id, className }: { id: string | null; className?: string }) {
  const { data: investigation, isPending, isError, refetch, isRefetching } = useInvestigation(id)

  return (
    <Card className={className}>
      <CardHeader>
        <CardTitle>Current investigation</CardTitle>
        <CardDescription>Case summary and position in the FALCON workflow.</CardDescription>
      </CardHeader>
      <CardContent>
        {id === null ? (
          <EmptyState
            icon={FolderSearch}
            title="No investigation selected"
            description="Choose an investigation from the selector in the top bar."
          />
        ) : isPending ? (
          <div className="space-y-3">
            <Skeleton className="h-6 w-2/3" />
            <Skeleton className="h-16 w-full" />
          </div>
        ) : isError ? (
          <ErrorState
            description="The investigation could not be loaded. Check your connection and try again."
            onRetry={() => refetch()}
            retrying={isRefetching}
          />
        ) : !investigation ? (
          <EmptyState
            icon={FolderSearch}
            title="Investigation not found"
            description="It may have been archived or you may no longer have access."
          />
        ) : (
          <div className="space-y-5">
            <div className="flex flex-wrap items-center gap-2">
              <IdTag>{investigation.id}</IdTag>
              <h2 className="text-lg font-semibold">{investigation.title}</h2>
            </div>
            <dl className="grid grid-cols-2 gap-x-6 gap-y-3 text-sm sm:grid-cols-4">
              <Detail label="Status">
                <StatusBadge kind="investigation" status={investigation.status} />
              </Detail>
              <Detail label="Priority">
                <PriorityBadge priority={investigation.priority} />
              </Detail>
              <Detail label="Case type">{investigation.caseType}</Detail>
              <Detail label="Lead investigator">{investigation.leadInvestigator}</Detail>
              <Detail label="Location">{investigation.location}</Detail>
              <Detail label="Last updated">{formatDateTime(investigation.updatedAt)}</Detail>
            </dl>
            <div className="space-y-2">
              <p className="text-xs font-medium text-muted-foreground">Workflow</p>
              <WorkflowStepper stage={investigation.stage} className="flex-wrap" />
            </div>
            <div className="flex flex-wrap items-center justify-between gap-3 rounded-md bg-muted/60 px-3 py-2">
              <p className="text-sm">
                <span className="font-medium">Next step: </span>
                {nextStepByStage[investigation.stage]}
              </p>
              <Button asChild variant="outline" size="sm">
                <Link to="/evidence">
                  Open evidence <ArrowRight />
                </Link>
              </Button>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  )
}

function Detail({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1">
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd>{children}</dd>
    </div>
  )
}

function InvestigationsTable() {
  const { data: investigations, isPending } = useInvestigations()
  const { currentInvestigationId, setCurrentInvestigation } = useInvestigationContext()

  return (
    <Card>
      <CardHeader>
        <CardTitle>Investigations</CardTitle>
        <CardDescription>Select a row to make it the current investigation.</CardDescription>
      </CardHeader>
      <CardContent className="px-0">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="pl-6">ID</TableHead>
              <TableHead>Title</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Priority</TableHead>
              <TableHead className="hidden md:table-cell">Lead</TableHead>
              <TableHead className="hidden pr-6 lg:table-cell">Last updated</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isPending
              ? Array.from({ length: 4 }, (_, i) => (
                  <TableRow key={i}>
                    <TableCell colSpan={6} className="px-6">
                      <Skeleton className="h-5 w-full" />
                    </TableCell>
                  </TableRow>
                ))
              : investigations?.map((investigation) => {
                  const selected = investigation.id === currentInvestigationId
                  return (
                    <TableRow
                      key={investigation.id}
                      data-state={selected ? 'selected' : undefined}
                      className="cursor-pointer"
                      onClick={() => setCurrentInvestigation(investigation.id)}
                    >
                      <TableCell className="pl-6">
                        {/* A real button keeps rows usable by keyboard and screen readers */}
                        <button
                          type="button"
                          onClick={() => setCurrentInvestigation(investigation.id)}
                          aria-pressed={selected}
                          aria-label={`Make ${investigation.id} the current investigation`}
                          className="rounded outline-none focus-visible:ring-2 focus-visible:ring-ring"
                        >
                          <IdTag className={cn(selected && 'border-primary/40 text-primary')}>
                            {investigation.id}
                          </IdTag>
                        </button>
                      </TableCell>
                      <TableCell className="max-w-72 truncate font-medium">{investigation.title}</TableCell>
                      <TableCell>
                        <StatusBadge kind="investigation" status={investigation.status} />
                      </TableCell>
                      <TableCell>
                        <PriorityBadge priority={investigation.priority} />
                      </TableCell>
                      <TableCell className="hidden text-muted-foreground md:table-cell">
                        {investigation.leadInvestigator}
                      </TableCell>
                      <TableCell className="hidden pr-6 text-muted-foreground tabular-nums lg:table-cell">
                        {formatDateTime(investigation.updatedAt)}
                      </TableCell>
                    </TableRow>
                  )
                })}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  )
}
