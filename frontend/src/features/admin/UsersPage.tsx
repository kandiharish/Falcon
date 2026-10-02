import { useState } from 'react'
import { KeyRound, Lock, LockOpen, MoreHorizontal, Pencil, ShieldCheck, ShieldOff, UserCheck, UserPlus, UserX, Users } from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
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
import type { UserSummary } from '@/domain/types'
import { ApiError } from '@/services/apiClient'
import { can } from '@/services/authService'
import { useCurrentUser, useUserAdmin, useUsers } from '@/services/queries'
import { UserDialogs, type UserDialogState } from './UserDialogs'
import { PageHeader } from '@/design-system/PageHeader'
import { EmptyState, ErrorState } from '@/design-system/states'
import { toneBadgeClass, type Tone } from '@/design-system/tones'
import { roleLabels } from '@/design-system/vocabulary'
import { formatDateTime } from '@/lib/format'
import { cn } from '@/lib/utils'

/** Administration → Users (plan §31): accounts, roles and account security. */
export function UsersPage() {
  const { data: users, isPending, isError, error, refetch, isFetching } = useUsers()
  const { data: me } = useCurrentUser()
  const canManage = can(me, 'users:manage')
  const [dialog, setDialog] = useState<UserDialogState>(null)

  return (
    <div className="mx-auto max-w-7xl space-y-6">
      <PageHeader
        eyebrow="Administration"
        title="Users"
        description="Everyone with access to FALCON, their role and account security status."
        actions={canManage && <Button onClick={() => setDialog({ kind: 'create' })}><UserPlus /> New user</Button>}
      />
      <Card>
        <CardHeader>
          <CardTitle>Accounts</CardTitle>
          <CardDescription>
            Roles decide what each person can see and do. Permissions are enforced by the server
            on every request.
          </CardDescription>
        </CardHeader>
        <CardContent className="px-0">
          {isError ? (
            <div className="px-6">
              <ErrorState
                description={error instanceof ApiError ? error.message : 'Users could not be loaded.'}
                onRetry={() => refetch()}
                retrying={isFetching}
              />
            </div>
          ) : !isPending && users.length === 0 ? (
            <div className="px-6">
              <EmptyState icon={Users} title="No users yet" description="Accounts created by administrators appear here." />
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="pl-6">Name</TableHead>
                  <TableHead>Role</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="hidden md:table-cell">MFA</TableHead>
                  <TableHead className="hidden lg:table-cell">Last sign-in</TableHead>
                  {canManage && <TableHead className="w-12 pr-6"><span className="sr-only">Actions</span></TableHead>}
                </TableRow>
              </TableHeader>
              <TableBody>
                {isPending
                  ? Array.from({ length: 5 }, (_, i) => (
                      <TableRow key={i}>
                        <TableCell colSpan={6} className="px-6">
                          <Skeleton className="h-8 w-full" />
                        </TableCell>
                      </TableRow>
                    ))
                  : users.map((user) => (
                      <UserRow key={user.id} user={user} isMe={user.id === me?.id} canManage={canManage} onAction={setDialog} />
                    ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
      {dialog && <UserDialogs state={dialog} onClose={() => setDialog(null)} />}
    </div>
  )
}

function UserRow({ user, isMe, canManage, onAction }: { user: UserSummary; isMe: boolean; canManage: boolean; onAction: (s: UserDialogState) => void }) {
  const admin = useUserAdmin()
  const unlock = () =>
    admin.mutate({ kind: 'unlock', id: user.id }, {
      onSuccess: () => toast.success(`${user.displayName} unlocked`),
      onError: (err) => toast.error('Could not unlock', { description: err instanceof ApiError ? err.message : undefined }),
    })
  return (
    <TableRow>
      <TableCell className="pl-6">
        <p className="font-medium">{user.displayName}</p>
        <p className="font-mono text-xs text-muted-foreground">{user.email}</p>
      </TableCell>
      <TableCell>
        <Pill tone="info" icon={KeyRound}>{roleLabels[user.role]}</Pill>
      </TableCell>
      <TableCell>
        {!user.isActive ? (
          <Pill tone="neutral" icon={UserX}>Deactivated</Pill>
        ) : user.locked ? (
          <Pill tone="danger" icon={Lock}>Locked</Pill>
        ) : (
          <Pill tone="success" icon={UserCheck}>Active</Pill>
        )}
      </TableCell>
      <TableCell className="hidden md:table-cell">
        {user.mfaEnabled ? (
          <Pill tone="success" icon={ShieldCheck}>Enabled</Pill>
        ) : (
          <Pill tone="warning" icon={ShieldOff}>Not enrolled</Pill>
        )}
      </TableCell>
      <TableCell className="hidden text-muted-foreground tabular-nums lg:table-cell">
        {user.lastLoginAt ? formatDateTime(user.lastLoginAt) : 'Never'}
      </TableCell>
      {canManage && (
        <TableCell className="pr-6">
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="icon-sm" aria-label={`Actions for ${user.displayName}`}><MoreHorizontal /></Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-56">
              <DropdownMenuItem onSelect={() => onAction({ kind: 'edit', user })}><Pencil /> Edit name and role</DropdownMenuItem>
              <DropdownMenuItem onSelect={() => onAction({ kind: 'password', user })}><KeyRound /> Set temporary password</DropdownMenuItem>
              {user.locked && <DropdownMenuItem onSelect={unlock}><LockOpen /> Unlock account</DropdownMenuItem>}
              <DropdownMenuSeparator />
              <DropdownMenuItem disabled={isMe} onSelect={() => onAction({ kind: 'active', user })} className={user.isActive ? 'text-destructive' : undefined}>
                {user.isActive ? <><UserX /> Deactivate…</> : <><UserCheck /> Reactivate…</>}
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </TableCell>
      )}
    </TableRow>
  )
}

function Pill({ tone, icon: Icon, children }: { tone: Tone; icon: typeof Lock; children: string }) {
  return (
    <span
      className={cn(
        'inline-flex h-5.5 items-center gap-1 rounded-md border px-1.5 text-xs font-medium whitespace-nowrap',
        toneBadgeClass[tone],
      )}
    >
      <Icon aria-hidden className="size-3.5" />
      {children}
    </span>
  )
}
