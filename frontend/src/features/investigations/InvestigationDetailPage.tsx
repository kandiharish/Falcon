import { useEffect } from 'react'
import { Link, useParams } from 'react-router'
import {
  Activity,
  ArrowLeft,
  ChevronDown,
  FileStack,
  FolderSearch,
  Link2,
  MapPin,
  Tag,
  UserRoundSearch,
} from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import type { Investigation, InvestigationStatus } from '@/domain/types'
import { useInvestigationContext } from '@/app/investigation-context'
import { ApiError } from '@/services/apiClient'
import { can } from '@/services/authService'
import { useCurrentUser, useInvestigation, useUpdateInvestigation } from '@/services/queries'
import { PriorityBadge, StatusBadge } from '@/design-system/badges'
import { IdTag } from '@/design-system/IdTag'
import { PageHeader } from '@/design-system/PageHeader'
import { EmptyState, ErrorState } from '@/design-system/states'
import { WorkflowStepper } from '@/design-system/WorkflowStepper'
import { allowedTransitions, investigationStatusTerms, transitionLabels } from '@/design-system/vocabulary'
import { formatDateTime } from '@/lib/format'
import { allTimeZones, zoneLabel } from '@/lib/time'
import { ActivityTab } from './ActivityTab'
import { CourtPackCard, KeyLeadsCard, ReplayCard, SuggestionsCard } from './CaseCommandCenter'
import { TeamTab } from './TeamTab'

/** Investigation details (plan §10, §55): the case's home page. */
export function InvestigationDetailPage() {
  const { reference = '' } = useParams()
  const { data: investigation, isPending, isError, error, refetch, isFetching } = useInvestigation(reference)
  const setCurrentInvestigation = useInvestigationContext((s) => s.setCurrentInvestigation)

  // Opening a case makes it the current investigation everywhere (top bar, context strip).
  useEffect(() => {
    if (investigation) setCurrentInvestigation(investigation.reference)
  }, [investigation, setCurrentInvestigation])

  if (isPending) {
    return (
      <div className="mx-auto max-w-7xl space-y-4">
        <Skeleton className="h-6 w-40" />
        <Skeleton className="h-8 w-2/3" />
        <Skeleton className="h-64 w-full" />
      </div>
    )
  }

  if (isError) {
    const notFound = error instanceof ApiError && error.status === 404
    return (
      <div className="mx-auto max-w-3xl pt-6">
        {notFound ? (
          <EmptyState
            icon={FolderSearch}
            title="Investigation not found"
            description="It does not exist, or you are not on its team. Ask the lead investigator to add you."
            action={
              <Button asChild variant="outline">
                <Link to="/investigations">Back to investigations</Link>
              </Button>
            }
          />
        ) : (
          <ErrorState
            description={error instanceof ApiError ? error.message : 'The investigation could not be loaded.'}
            onRetry={() => refetch()}
            retrying={isFetching}
          />
        )}
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-7xl space-y-6">
      <Button asChild variant="ghost" size="sm" className="-ml-2 text-muted-foreground">
        <Link to="/investigations">
          <ArrowLeft /> Investigations
        </Link>
      </Button>

      <PageHeader
        eyebrow={
          <span className="flex flex-wrap items-center gap-2">
            <IdTag>{investigation.reference}</IdTag>
            <StatusBadge kind="investigation" status={investigation.status} />
            <PriorityBadge priority={investigation.priority} />
          </span>
        }
        title={investigation.title}
        description={`${investigation.caseType} · Lead: ${investigation.leadInvestigator.displayName}`}
        actions={<StatusActions investigation={investigation} />}
      />

      <Tabs defaultValue="overview">
        <TabsList>
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="team">Team ({investigation.teamSize})</TabsTrigger>
          <TabsTrigger value="activity">Activity</TabsTrigger>
        </TabsList>
        <TabsContent value="overview" className="pt-4">
          <OverviewTab investigation={investigation} />
        </TabsContent>
        <TabsContent value="team" className="pt-4">
          <TeamTab investigation={investigation} />
        </TabsContent>
        <TabsContent value="activity" className="pt-4">
          <ActivityTab reference={investigation.reference} />
        </TabsContent>
      </Tabs>
    </div>
  )
}

/** Status changes the user is allowed to make right now. */
function StatusActions({ investigation }: { investigation: Investigation }) {
  const { data: user } = useCurrentUser()
  const update = useUpdateInvestigation(investigation.reference)
  const canEdit =
    can(user, 'investigation:write') && (investigation.myRoleInCase !== null || user?.role === 'supervisor')
  const next = allowedTransitions[investigation.status]

  if (!canEdit || next.length === 0) return null

  const move = (status: InvestigationStatus) =>
    update.mutate(
      { status },
      {
        onSuccess: () => toast.success(`Status changed to ${investigationStatusTerms[status].label}`),
        onError: (err) =>
          toast.error('Status could not be changed', {
            description: err instanceof ApiError ? err.message : undefined,
          }),
      },
    )

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="outline" disabled={update.isPending}>
          {update.isPending ? 'Updating…' : 'Change status'} <ChevronDown />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuLabel>Move to</DropdownMenuLabel>
        <DropdownMenuSeparator />
        {next.map((status) => {
          const Icon = investigationStatusTerms[status].icon
          return (
            <DropdownMenuItem key={status} onSelect={() => move(status)}>
              <Icon /> {transitionLabels[status]}
            </DropdownMenuItem>
          )
        })}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

/** The case's time zone; editors can change it (it changes how times are shown and read). */
function TimeZoneField({ investigation }: { investigation: Investigation }) {
  const { data: user } = useCurrentUser()
  const update = useUpdateInvestigation(investigation.reference)
  const canEdit =
    can(user, 'investigation:write') &&
    (investigation.myRoleInCase !== null || user?.role === 'supervisor') &&
    investigation.status !== 'archived'
  if (!canEdit) return <>{zoneLabel(investigation.timeZone)}</>
  return (
    <Select
      value={investigation.timeZone}
      disabled={update.isPending}
      onValueChange={(timeZone) =>
        update.mutate(
          { timeZone },
          {
            onSuccess: () => toast.success(`Time zone set to ${zoneLabel(timeZone)}`),
            onError: (err) => toast.error('Time zone not changed', { description: err instanceof ApiError ? err.message : undefined }),
          },
        )
      }
    >
      <SelectTrigger size="sm" className="w-full max-w-64" aria-label="Investigation time zone">
        <SelectValue />
      </SelectTrigger>
      <SelectContent className="max-h-72">
        {/* Browsers list some zones under older names (Chromium: Asia/Calcutta for Asia/Kolkata):
            always offer the case's own zone so the picker never shows blank. */}
        {[...new Set([investigation.timeZone, ...allTimeZones()])].map((zone) => (
          <SelectItem key={zone} value={zone}>{zoneLabel(zone)}</SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}

function OverviewTab({ investigation }: { investigation: Investigation }) {
  const counts = [
    { label: 'Evidence items', value: investigation.counts.evidence, icon: FileStack, phase: 5 },
    { label: 'Entities', value: investigation.counts.entities, icon: UserRoundSearch, phase: 6 },
    { label: 'Events', value: investigation.counts.events, icon: Activity, phase: 6 },
    { label: 'Correlations', value: investigation.counts.correlations, icon: Link2, phase: 8 },
  ]

  return (
    <div className="grid gap-6 lg:grid-cols-3">
      <div className="space-y-6 lg:col-span-2">
        <Card>
          <CardHeader>
            <CardTitle>Case summary</CardTitle>
          </CardHeader>
          <CardContent className="space-y-5">
            <p className="text-sm whitespace-pre-line">
              {investigation.description || <span className="text-muted-foreground">No description yet.</span>}
            </p>
            <dl className="grid grid-cols-2 gap-x-6 gap-y-3 text-sm sm:grid-cols-3">
              <Detail label="Case type">{investigation.caseType}</Detail>
              <Detail label="Lead investigator">{investigation.leadInvestigator.displayName}</Detail>
              <Detail label="Your role">
                {investigation.myRoleInCase === 'lead'
                  ? 'Lead investigator'
                  : investigation.myRoleInCase === 'member'
                    ? 'Team member'
                    : 'Supervisor oversight'}
              </Detail>
              <Detail label="Location">
                {investigation.location ? (
                  <span className="inline-flex items-center gap-1">
                    <MapPin aria-hidden className="size-3.5 text-muted-foreground" />
                    {investigation.location}
                  </span>
                ) : (
                  '—'
                )}
              </Detail>
              <Detail label="Time zone">
                <TimeZoneField investigation={investigation} />
              </Detail>
              <Detail label="Created">{formatDateTime(investigation.createdAt)}</Detail>
              <Detail label="Last updated">{formatDateTime(investigation.updatedAt)}</Detail>
            </dl>
            {investigation.tags.length > 0 && (
              <div className="flex flex-wrap items-center gap-1.5">
                <Tag aria-hidden className="size-3.5 text-muted-foreground" />
                {investigation.tags.map((tag) => (
                  <span key={tag} className="rounded-md bg-muted px-1.5 py-0.5 text-xs">{tag}</span>
                ))}
              </div>
            )}
            <div className="space-y-2">
              <p className="text-xs font-medium text-muted-foreground">Workflow</p>
              <WorkflowStepper stage={investigation.stage} className="flex-wrap" />
            </div>
          </CardContent>
        </Card>

        <SuggestionsCard investigation={investigation} />
      </div>
      <div className="space-y-6">
        <KeyLeadsCard investigation={investigation} />
        <ReplayCard />
        <CourtPackCard investigation={investigation} />
        <Card>
          <CardHeader>
            <CardTitle>Case contents</CardTitle>
            <CardDescription>Filled as evidence is added and analysed.</CardDescription>
            <CardAction>
              <Button asChild variant="outline" size="sm">
                <Link to="/evidence">Open evidence</Link>
              </Button>
            </CardAction>
          </CardHeader>
          <CardContent>
            <ul className="divide-y text-sm">
              {counts.map(({ label, value, icon: Icon, phase }) => (
                <li key={label} className="flex items-center justify-between gap-3 py-2.5">
                  <span className="flex items-center gap-2 text-muted-foreground">
                    <Icon aria-hidden className="size-4" /> {label}
                  </span>
                  <span className="text-right">
                    <span className="font-mono tabular-nums">{value}</span>
                    {value === 0 && <span className="block text-[0.7rem] text-muted-foreground">Phase {phase}</span>}
                  </span>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      </div>
    </div>
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
