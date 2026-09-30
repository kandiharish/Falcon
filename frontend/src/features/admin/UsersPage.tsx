import { KeyRound, Lock, ShieldCheck, ShieldOff, UserCheck, UserX, Users } from 'lucide-react'
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
import { useUsers } from '@/services/queries'
import { PageHeader } from '@/design-system/PageHeader'
import { EmptyState, ErrorState } from '@/design-system/states'
import { toneBadgeClass, type Tone } from '@/design-system/tones'
import { roleLabels } from '@/design-system/vocabulary'
import { formatDateTime } from '@/lib/format'
import { cn } from '@/lib/utils'

/** Administration → Users (plan §31). Read-only in Phase 3; editing arrives with user management. */
export function UsersPage() {
  const { data: users, isPending, isError, error, refetch, isFetching } = useUsers()

  return (
    <div className="mx-auto max-w-7xl space-y-6">
      <PageHeader
        eyebrow="Administration"
        title="Users"
        description="Everyone with access to FALCON, their role and account security status."
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
                  <TableHead className="hidden pr-6 lg:table-cell">Last sign-in</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {isPending
                  ? Array.from({ length: 5 }, (_, i) => (
                      <TableRow key={i}>
                        <TableCell colSpan={5} className="px-6">
                          <Skeleton className="h-8 w-full" />
                        </TableCell>
                      </TableRow>
                    ))
                  : users.map((user) => <UserRow key={user.id} user={user} />)}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

function UserRow({ user }: { user: UserSummary }) {
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
      <TableCell className="hidden pr-6 text-muted-foreground tabular-nums lg:table-cell">
        {user.lastLoginAt ? formatDateTime(user.lastLoginAt) : 'Never'}
      </TableCell>
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
