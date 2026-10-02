import { useState } from 'react'
import { Link, useSearchParams } from 'react-router'
import { CalendarClock, FolderSearch, ListChecks, Plus, UserRound } from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import type { Task, TaskStatus } from '@/domain/types'
import { ApiError } from '@/services/apiClient'
import { useMyTasks, useSaveTask, useTasks } from '@/services/queries'
import { PriorityBadge, StatusBadge } from '@/design-system/badges'
import { IdTag } from '@/design-system/IdTag'
import { PageHeader } from '@/design-system/PageHeader'
import { EmptyState, ErrorState } from '@/design-system/states'
import { taskStatusTerms } from '@/design-system/vocabulary'
import { cn } from '@/lib/utils'
import { EvidenceChip } from '@/features/extraction/components'
import { useCaseAccess, useCurrentCase } from '@/features/extraction/useCaseAccess'
import { TaskDialog } from './TaskDialog'

const COLUMNS: TaskStatus[] = ['todo', 'in_progress', 'review', 'completed']
type Scope = 'case' | 'mine'

/** Today as YYYY-MM-DD (it changes only at midnight, so reading it while rendering is fine). */
const today = () => new Date().toISOString().slice(0, 10)

/** Investigation tasks (plan §30) as a board: To Do → In Progress → Review → Completed. */
export function TasksPage() {
  const current = useCurrentCase()
  const [params, setParams] = useSearchParams()
  // A notification links to ?case=…&task=…: open that task, in that case.
  const caseRef = params.get('case') ?? current
  const [scope, setScope] = useState<Scope>('case')
  const [editing, setEditing] = useState<{ caseRef: string; task?: Task } | null>(null)
  const { canManageTasks } = useCaseAccess(caseRef)
  const caseTasks = useTasks(scope === 'case' ? caseRef : null)
  const mine = useMyTasks()
  const query = scope === 'case' ? caseTasks : mine

  if (!caseRef && scope === 'case') {
    return (
      <div className="mx-auto max-w-3xl pt-6">
        <EmptyState icon={FolderSearch} title="No investigation selected" description="Choose an investigation in the top bar, or look at the tasks assigned to you."
          action={<Button variant="outline" onClick={() => setScope('mine')}>My tasks</Button>} />
      </div>
    )
  }

  const tasks = query.data ?? []
  // The URL is the source of truth, so a notification clicked while this page is open works too.
  const opened = params.get('task')
  const deepLinked = opened ? tasks.find((t) => t.reference === opened) : undefined
  const dialog = editing ?? (deepLinked ? { caseRef: deepLinked.investigationReference, task: deepLinked } : null)
  const closeDialog = () => {
    setEditing(null)
    if (opened) {
      const next = new URLSearchParams(params)
      next.delete('task')
      setParams(next, { replace: true })
    }
  }

  return (
    <div className="mx-auto max-w-7xl space-y-5">
      <PageHeader
        eyebrow={scope === 'case' && caseRef ? <IdTag>{caseRef}</IdTag> : 'All my investigations'}
        title="Tasks"
        description="Investigation work for the team. The person assigned is notified, and every change is recorded."
        actions={
          <>
            <Tabs value={scope} onValueChange={(v) => setScope(v as Scope)}>
              <TabsList>
                <TabsTrigger value="case">This investigation</TabsTrigger>
                <TabsTrigger value="mine">Assigned to me</TabsTrigger>
              </TabsList>
            </Tabs>
            {scope === 'case' && canManageTasks && caseRef && (
              <Button onClick={() => setEditing({ caseRef })}><Plus /> New task</Button>
            )}
          </>
        }
      />

      {query.isError ? (
        <ErrorState description={query.error instanceof ApiError ? query.error.message : 'Tasks could not be loaded.'} onRetry={() => query.refetch()} retrying={query.isFetching} />
      ) : query.isPending ? (
        <Skeleton className="h-96 w-full" />
      ) : tasks.length === 0 ? (
        <EmptyState icon={ListChecks} title={scope === 'mine' ? 'Nothing assigned to you' : 'No tasks yet'}
          description={scope === 'mine' ? 'Open tasks assigned to you, in any investigation, appear here.' : 'Create a task to plan the next steps of this investigation.'} />
      ) : (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          {COLUMNS.filter((c) => scope === 'case' || c !== 'completed').map((status) => {
            const column = tasks.filter((t) => t.status === status)
            const term = taskStatusTerms[status]
            return (
              <section key={status} aria-label={term.label} className="space-y-2 rounded-lg border bg-muted/30 p-2">
                <h2 className="flex items-center gap-2 px-1 py-1 text-sm font-semibold">
                  <term.icon aria-hidden className="size-4 text-muted-foreground" /> {term.label}
                  <span className="ml-auto rounded-full bg-muted px-2 text-xs text-muted-foreground tabular-nums">{column.length}</span>
                </h2>
                {column.map((task) => (
                  <TaskCard key={`${task.investigationReference}-${task.reference}`} task={task} showCase={scope === 'mine'}
                    canManage={scope === 'case' ? canManageTasks : true}
                    onOpen={() => setEditing({ caseRef: task.investigationReference, task })} />
                ))}
                {column.length === 0 && <p className="px-1 py-4 text-center text-xs text-muted-foreground">Nothing here</p>}
              </section>
            )
          })}
        </div>
      )}

      {dialog && (
        <TaskDialog key={dialog.task?.reference ?? 'new'} caseRef={dialog.caseRef} task={dialog.task}
          readOnly={scope === 'case' && !canManageTasks} onClose={closeDialog} />
      )}
    </div>
  )
}

function TaskCard({ task, showCase, canManage, onOpen }: { task: Task; showCase: boolean; canManage: boolean; onOpen: () => void }) {
  const save = useSaveTask(task.investigationReference)
  const overdue = task.dueDate && task.status !== 'completed' && task.dueDate < today()
  const move = (status: TaskStatus) =>
    save.mutate(
      { reference: task.reference, input: { status } },
      {
        onSuccess: () => toast.success(`${task.reference} moved to ${taskStatusTerms[status].label}`),
        onError: (err) => toast.error('Could not move the task', { description: err instanceof ApiError ? err.message : undefined }),
      },
    )
  return (
    <Card className="gap-2 py-3">
      <CardContent className="space-y-2 px-3">
        <button type="button" onClick={onOpen} className="block w-full space-y-1 text-left outline-none focus-visible:ring-2 focus-visible:ring-ring">
          <span className="flex items-center gap-2">
            <span className="font-mono text-xs text-muted-foreground">{task.reference}</span>
            {showCase && <span className="font-mono text-xs text-muted-foreground">· {task.investigationReference}</span>}
            <PriorityBadge priority={task.priority} className="ml-auto" />
          </span>
          <span className="block text-sm font-medium">{task.title}</span>
        </button>
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
          <span className="inline-flex items-center gap-1"><UserRound aria-hidden className="size-3.5" />{task.assignee?.displayName ?? 'Unassigned'}</span>
          {task.dueDate && (
            <span className={cn('inline-flex items-center gap-1', overdue && 'font-medium text-destructive')}>
              <CalendarClock aria-hidden className="size-3.5" />{overdue ? 'Overdue · ' : 'Due '}{task.dueDate}
            </span>
          )}
        </div>
        {task.evidence.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {task.evidence.map((ref) => <EvidenceChip key={ref} reference={ref} caseRef={task.investigationReference} />)}
          </div>
        )}
        {canManage ? (
          <Select value={task.status} onValueChange={(v) => move(v as TaskStatus)} disabled={save.isPending}>
            <SelectTrigger size="sm" className="w-full" aria-label={`Move ${task.reference}`}><SelectValue /></SelectTrigger>
            <SelectContent>
              {COLUMNS.map((s) => <SelectItem key={s} value={s}>{taskStatusTerms[s].label}</SelectItem>)}
            </SelectContent>
          </Select>
        ) : (
          <StatusBadge kind="task" status={task.status} />
        )}
        {showCase && (
          <Link to={`/investigations/${task.investigationReference}`} className="block truncate text-xs text-muted-foreground hover:underline">{task.investigationTitle}</Link>
        )}
      </CardContent>
    </Card>
  )
}
