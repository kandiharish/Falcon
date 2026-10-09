import { useState } from 'react'
import { ArrowRight, FolderSearch, Settings } from 'lucide-react'
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
import { can } from '@/services/authService'
import { useCurrentUser, useDashboard, useInvestigation, useInvestigations } from '@/services/queries'
import type { WorkflowStage } from '@/domain/types'
import { PriorityBadge, StatusBadge } from '@/design-system/badges'
import { IdTag } from '@/design-system/IdTag'
import { PageHeader } from '@/design-system/PageHeader'
import { EmptyState, ErrorState } from '@/design-system/states'
import { WorkflowStepper } from '@/design-system/WorkflowStepper'
import { formatDateTime } from '@/lib/format'
import { cn } from '@/lib/utils'
import { SystemStatusCard } from './SystemStatusCard'
import {
  ActivityFeed,
  AlertsList,
  BarList,
  ColumnChart,
  MetricTiles,
  MyTasks,
  Panel,
  PendingReviews,
  RecentEvidence,
} from './DashboardSections'
import { sourceItems, statusItems } from './dashboardItems'

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
  const { data: user } = useCurrentUser()

  // Roles without case access (e.g. system administrator) get a system-focused overview.
  if (!can(user, 'investigation:read')) return <SystemOverview />

  return <CommandCenter currentId={currentId} />
}

function greetingNow() {
  const now = new Date()
  const hour = now.getHours()
  return {
    greeting: hour < 12 ? 'Good morning' : hour < 17 ? 'Good afternoon' : 'Good evening',
    date: now.toLocaleDateString('en-GB', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' }),
  }
}

function CommandCenter({ currentId }: { currentId: string | null }) {
  const { data, isPending, isError, refetch, isFetching } = useDashboard(true)
  const { data: user } = useCurrentUser()
  const [today] = useState(greetingNow) // read the clock once, not on every render
  return (
    <div className="mx-auto max-w-7xl space-y-6">
      <PageHeader
        eyebrow={<span className="text-xs text-muted-foreground">{today.greeting}{user ? `, ${user.displayName}` : ''} · {today.date}</span>}
        title="Command center"
        description="Across the investigations you work on: what is happening, what needs review, and what is assigned to you."
      />
      {isError ? (
        <ErrorState description="The dashboard could not be loaded." onRetry={() => refetch()} retrying={isFetching} />
      ) : isPending ? (
        <Skeleton className="h-40 w-full" />
      ) : (
        <>
          <MetricTiles metrics={data.metrics} />
          <div className="grid gap-6 lg:grid-cols-3">
            <Panel className="lg:col-span-2" title="Leads waiting for review"
              description="Potential relationships no one has judged yet, strongest first. Each one says why it exists."
              action={<Button asChild variant="outline" size="sm"><Link to="/correlations">All correlations <ArrowRight /></Link></Button>}>
              <PendingReviews items={data.pending_correlations} />
              {Object.keys(data.correlations_by_level).length > 0 && (
                <div className="mt-4 border-t pt-3">
                  <BarList tone="signal" empty="" items={['high', 'medium', 'low'].filter((l) => data.correlations_by_level[l]).map((l) => ({ label: `${l[0].toUpperCase()}${l.slice(1)}`, value: data.correlations_by_level[l] }))} />
                </div>
              )}
            </Panel>
            <Panel title="Needs attention" description="Failures, integrity problems and overdue tasks.">
              <AlertsList alerts={data.alerts} />
            </Panel>
          </div>
          <div className="grid gap-6 lg:grid-cols-3">
            <CurrentInvestigationCard id={currentId} className="lg:col-span-2" />
            <Panel title="Assigned to you"><MyTasks items={data.my_tasks} /></Panel>
          </div>
          <div className="grid gap-6 lg:grid-cols-3">
            <Panel className="lg:col-span-2" title="Event activity"
              description={data.event_activity.unit === 'hour' ? 'Events per hour across your investigations (your local time).' : 'Events per day across your investigations.'}>
              <ColumnChart buckets={data.event_activity.buckets} unit={data.event_activity.unit as 'hour' | 'day'} label="Events over time" />
            </Panel>
            <Panel title="Evidence sources">
              <div className="space-y-5">
                <BarList items={sourceItems(data.evidence_by_type)} empty="No evidence yet." />
                <div className="space-y-2">
                  <p className="text-xs font-medium text-muted-foreground">Processing status</p>
                  <BarList items={statusItems(data.evidence_by_status)} tone="success" empty="No evidence yet." />
                </div>
              </div>
            </Panel>
          </div>
          <div className="grid gap-6 lg:grid-cols-3">
            <InvestigationsTable className="lg:col-span-2" />
            <div className="space-y-6">
              <Panel title="Recent evidence"><RecentEvidence items={data.recent_evidence} /></Panel>
              <Panel title="Investigation activity" description="Recorded actions, from the audit log."><ActivityFeed entries={data.activity} days={data.activity_by_day} /></Panel>
            </div>
          </div>
        </>
      )}
    </div>
  )
}

function SystemOverview() {
  const { data: user } = useCurrentUser()
  return (
    <div className="mx-auto max-w-7xl space-y-6">
      <PageHeader
        title="System overview"
        description="Your role manages the FALCON platform. Investigation data is not visible to this role."
      />
      <div className="grid gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Administration</CardTitle>
            <CardDescription>Manage who can access FALCON and what each role may do.</CardDescription>
          </CardHeader>
          <CardContent className="flex flex-wrap gap-2">
            {can(user, 'users:read') && (
              <Button asChild variant="outline">
                <Link to="/admin">
                  <Settings /> Users and roles
                </Link>
              </Button>
            )}
          </CardContent>
        </Card>
        <SystemStatusCard />
      </div>
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
              <IdTag>{investigation.reference}</IdTag>
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
              <Detail label="Lead investigator">{investigation.leadInvestigator.displayName}</Detail>
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
                <Link to={`/investigations/${investigation.reference}`}>
                  Open investigation <ArrowRight />
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

function InvestigationsTable({ className }: { className?: string }) {
  const { data: page, isPending } = useInvestigations({ limit: 10 })
  const investigations = page?.items
  const { currentInvestigationId, setCurrentInvestigation } = useInvestigationContext()

  return (
    <Card className={className}>
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
                  const selected = investigation.reference === currentInvestigationId
                  return (
                    <TableRow
                      key={investigation.reference}
                      data-state={selected ? 'selected' : undefined}
                      className="cursor-pointer"
                      onClick={() => setCurrentInvestigation(investigation.reference)}
                    >
                      <TableCell className="pl-6">
                        {/* A real button keeps rows usable by keyboard and screen readers */}
                        <button
                          type="button"
                          onClick={() => setCurrentInvestigation(investigation.reference)}
                          aria-pressed={selected}
                          aria-label={`Make ${investigation.reference} the current investigation`}
                          className="rounded outline-none focus-visible:ring-2 focus-visible:ring-ring"
                        >
                          <IdTag className={cn(selected && 'border-primary/40 text-primary')}>
                            {investigation.reference}
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
                        {investigation.leadInvestigator.displayName}
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
