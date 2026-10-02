import { useState } from 'react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'
import type { Priority, Task, TaskStatus } from '@/domain/types'
import { ApiError } from '@/services/apiClient'
import { useEvidenceList, useInvestigationMembers, useSaveTask } from '@/services/queries'
import { priorityTerms, taskStatusTerms } from '@/design-system/vocabulary'

const NOBODY = 'nobody'

interface Props {
  caseRef: string
  /** The task to edit; leave out to create a new one. */
  task?: Task
  readOnly?: boolean
  onClose: () => void
}

/** Create or edit a task. Mount it with a `key` per task so the form starts from that task. */
export function TaskDialog({ caseRef, task, readOnly = false, onClose }: Props) {
  const save = useSaveTask(caseRef)
  const { data: members } = useInvestigationMembers(caseRef)
  const { data: evidence, isError: evidenceFailed } = useEvidenceList(caseRef, { limit: 100 })
  const [title, setTitle] = useState(task?.title ?? '')
  const [description, setDescription] = useState(task?.description ?? '')
  const [status, setStatus] = useState<TaskStatus>(task?.status ?? 'todo')
  const [priority, setPriority] = useState<Priority>(task?.priority ?? 'medium')
  const [assignee, setAssignee] = useState(task?.assignee?.id ?? NOBODY)
  const [dueDate, setDueDate] = useState(task?.dueDate ?? '')
  const [linked, setLinked] = useState<string[]>(task?.evidence ?? [])
  const [error, setError] = useState<string | null>(null)

  const submit = (event: React.FormEvent) => {
    event.preventDefault()
    setError(null)
    save.mutate(
      {
        reference: task?.reference,
        input: {
          title: title.trim(),
          description,
          status,
          priority,
          assignee_id: assignee === NOBODY ? null : assignee,
          due_date: dueDate || null,
          evidence: linked,
        },
      },
      {
        onSuccess: (saved) => {
          toast.success(task ? `${saved.reference} saved` : `${saved.reference} created`)
          onClose()
        },
        onError: (err) => setError(err instanceof ApiError ? err.message : 'The task could not be saved.'),
      },
    )
  }

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>{task ? `${task.reference} · ${readOnly ? 'Task' : 'Edit task'}` : 'New task'}</DialogTitle>
          <DialogDescription>
            {task ? `Created by ${task.createdBy.displayName}. Every change is recorded in the audit log.` : 'A piece of investigation work for the team. The assignee is notified.'}
          </DialogDescription>
        </DialogHeader>
        <form id="task-form" onSubmit={submit} className="space-y-4">
          <fieldset disabled={readOnly || save.isPending} className="space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="task-title">Task name</Label>
              <Input id="task-title" value={title} onChange={(e) => setTitle(e.target.value)} required minLength={3} maxLength={200}
                placeholder="e.g. Verify the CCTV clock against GPS time" />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="task-description">Description</Label>
              <Textarea id="task-description" value={description} onChange={(e) => setDescription(e.target.value)} maxLength={5000} rows={3} />
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-1.5">
                <Label>Status</Label>
                <Select value={status} onValueChange={(v) => setStatus(v as TaskStatus)}>
                  <SelectTrigger className="w-full" aria-label="Status"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {Object.entries(taskStatusTerms).map(([value, term]) => <SelectItem key={value} value={value}>{term.label}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1.5">
                <Label>Priority</Label>
                <Select value={priority} onValueChange={(v) => setPriority(v as Priority)}>
                  <SelectTrigger className="w-full" aria-label="Priority"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {Object.entries(priorityTerms).map(([value, term]) => <SelectItem key={value} value={value}>{term.label}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1.5">
                <Label>Assigned to</Label>
                <Select value={assignee} onValueChange={setAssignee}>
                  <SelectTrigger className="w-full" aria-label="Assigned to"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value={NOBODY}>Nobody yet</SelectItem>
                    {members?.map((m) => <SelectItem key={m.userId} value={m.userId}>{m.displayName}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="task-due">Due date</Label>
                <Input id="task-due" type="date" value={dueDate} onChange={(e) => setDueDate(e.target.value)} />
              </div>
            </div>
            <div className="space-y-1.5">
              <Label>Related evidence</Label>
              <div className="max-h-36 space-y-1 overflow-y-auto rounded-md border p-2">
                {evidence?.items.length ? (
                  evidence.items.map((e) => (
                    <label key={e.reference} className="flex items-center gap-2 text-sm">
                      <Checkbox
                        checked={linked.includes(e.reference)}
                        onCheckedChange={(on) => setLinked((list) => (on ? [...list, e.reference] : list.filter((r) => r !== e.reference)))}
                      />
                      <span className="font-mono text-xs">{e.reference}</span>
                      <span className="truncate text-muted-foreground">{e.description || e.originalFilename}</span>
                    </label>
                  ))
                ) : (
                  <p className="text-xs text-muted-foreground">
                    {evidenceFailed ? 'The evidence list could not be loaded.' : evidence ? 'No evidence in this investigation yet.' : 'Loading…'}
                  </p>
                )}
              </div>
            </div>
          </fieldset>
          {error && <p className="text-sm text-destructive" role="alert">{error}</p>}
        </form>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>{readOnly ? 'Close' : 'Cancel'}</Button>
          {!readOnly && <Button type="submit" form="task-form" disabled={save.isPending || title.trim().length < 3}>{task ? 'Save' : 'Create task'}</Button>}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
