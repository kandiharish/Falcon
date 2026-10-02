import { useState } from 'react'
import { Crown, UserPlus } from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import type { Investigation } from '@/domain/types'
import { ApiError } from '@/services/apiClient'
import { can } from '@/services/authService'
import {
  useAddMember,
  useAssignableUsers,
  useCurrentUser,
  useInvestigationMembers,
} from '@/services/queries'
import { ErrorState } from '@/design-system/states'
import { roleLabels } from '@/design-system/vocabulary'
import { formatDateTime } from '@/lib/format'

/** Investigation team (plan §10): who can see and work on this case. */
export function TeamTab({ investigation }: { investigation: Investigation }) {
  const { data: user } = useCurrentUser()
  const { data: members, isPending, isError, refetch, isFetching } = useInvestigationMembers(investigation.reference)
  const [adding, setAdding] = useState(false)
  const canManage =
    can(user, 'investigation:write') &&
    (investigation.myRoleInCase !== null || user?.role === 'supervisor') &&
    investigation.status !== 'archived'

  if (isError) {
    return <ErrorState description="The team could not be loaded." onRetry={() => refetch()} retrying={isFetching} />
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-muted-foreground">
          Only team members (and supervisors) can see this investigation.
        </p>
        {canManage && (
          <Button variant="outline" onClick={() => setAdding(true)}>
            <UserPlus /> Add member
          </Button>
        )}
      </div>
      <Card className="gap-0 py-0">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="pl-4">Name</TableHead>
              <TableHead>Role</TableHead>
              <TableHead>On this case</TableHead>
              <TableHead className="hidden pr-4 md:table-cell">Added</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isPending
              ? Array.from({ length: 3 }, (_, i) => (
                  <TableRow key={i}>
                    <TableCell colSpan={4} className="px-4">
                      <Skeleton className="h-8 w-full" />
                    </TableCell>
                  </TableRow>
                ))
              : members.map((member) => (
                  <TableRow key={member.userId}>
                    <TableCell className="pl-4">
                      <p className="font-medium">{member.displayName}</p>
                      <p className="font-mono text-xs text-muted-foreground">{member.email}</p>
                    </TableCell>
                    <TableCell className="text-muted-foreground">{roleLabels[member.role]}</TableCell>
                    <TableCell>
                      {member.roleInCase === 'lead' ? (
                        <span className="inline-flex items-center gap-1 text-sm font-medium">
                          <Crown aria-hidden className="size-3.5 text-warning" /> Lead investigator
                        </span>
                      ) : (
                        <span className="text-sm">Team member</span>
                      )}
                    </TableCell>
                    <TableCell className="hidden pr-4 text-muted-foreground tabular-nums md:table-cell">
                      {formatDateTime(member.addedAt)}
                    </TableCell>
                  </TableRow>
                ))}
          </TableBody>
        </Table>
      </Card>
      {canManage && (
        <AddMemberDialog
          open={adding}
          onOpenChange={setAdding}
          reference={investigation.reference}
          existing={new Set(members?.map((m) => m.email))}
        />
      )}
    </div>
  )
}

function AddMemberDialog({
  open,
  onOpenChange,
  reference,
  existing,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  reference: string
  existing: Set<string>
}) {
  const { data: users, isPending } = useAssignableUsers(open)
  const add = useAddMember(reference)
  const [email, setEmail] = useState('')
  const candidates = users?.filter((u) => !existing.has(u.email)) ?? []

  const close = () => {
    setEmail('')
    add.reset()
    onOpenChange(false)
  }

  return (
    <Dialog open={open} onOpenChange={(next) => (next ? onOpenChange(true) : close())}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Add team member</DialogTitle>
          <DialogDescription>
            The person will be able to see this investigation and everything in it. This is recorded
            in the audit log.
          </DialogDescription>
        </DialogHeader>
        {add.error && (
          <p role="alert" className="rounded-md border border-destructive/25 bg-destructive/5 px-3 py-2 text-sm">
            {add.error instanceof ApiError ? add.error.message : 'The member could not be added.'}
          </p>
        )}
        <div className="space-y-1.5">
          <Label htmlFor="member">Person</Label>
          <Select value={email} onValueChange={setEmail} disabled={isPending}>
            <SelectTrigger id="member" className="w-full">
              <SelectValue placeholder={isPending ? 'Loading…' : 'Choose a person'} />
            </SelectTrigger>
            <SelectContent>
              {candidates.map((u) => (
                <SelectItem key={u.id} value={u.email}>
                  {u.displayName} · {roleLabels[u.role]}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          {!isPending && candidates.length === 0 && (
            <p className="text-xs text-muted-foreground">Everyone who can work on investigations is already on the team.</p>
          )}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={close}>Cancel</Button>
          <Button
            disabled={!email || add.isPending}
            onClick={() =>
              add.mutate(email, {
                onSuccess: (member) => {
                  toast.success(`${member.displayName} added to the team`)
                  close()
                },
              })
            }
          >
            {add.isPending ? 'Adding…' : 'Add to team'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
