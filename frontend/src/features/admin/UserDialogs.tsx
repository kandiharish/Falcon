import { useState } from 'react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import type { Role, UserSummary } from '@/domain/types'
import { ApiError } from '@/services/apiClient'
import { useUserAdmin } from '@/services/queries'
import { roleLabels } from '@/design-system/vocabulary'

export type UserDialogState =
  | { kind: 'create' }
  | { kind: 'edit'; user: UserSummary }
  | { kind: 'password'; user: UserSummary }
  | { kind: 'active'; user: UserSummary }
  | { kind: 'reset-mfa'; user: UserSummary }
  | null

const MIN_PASSWORD = 12

/** Create / edit / temporary password / (de)activate — one place, one set of rules. */
export function UserDialogs({ state, onClose }: { state: NonNullable<UserDialogState>; onClose: () => void }) {
  const admin = useUserAdmin()
  const user = state.kind === 'create' ? null : state.user
  const [email, setEmail] = useState('')
  const [name, setName] = useState(user?.displayName ?? '')
  const [role, setRole] = useState<Role>(user?.role ?? 'investigation_officer')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)

  const done = (message: string) => ({
    onSuccess: () => {
      toast.success(message)
      onClose()
    },
    onError: (err: Error) => setError(err instanceof ApiError ? err.message : 'The change could not be saved.'),
  })

  const submit = (event: React.FormEvent) => {
    event.preventDefault()
    setError(null)
    if (state.kind === 'create') {
      admin.mutate({ kind: 'create', input: { email, display_name: name, role, temporary_password: password } }, done(`${name} can now sign in`))
    } else if (state.kind === 'edit') {
      admin.mutate({ kind: 'update', id: state.user.id, input: { display_name: name, role } }, done('Saved'))
    } else if (state.kind === 'password') {
      admin.mutate({ kind: 'password', id: state.user.id, password }, done('Temporary password set'))
    } else if (state.kind === 'reset-mfa') {
      admin.mutate({ kind: 'reset-mfa', id: state.user.id }, done(`MFA reset for ${state.user.displayName}`))
    } else {
      admin.mutate(
        { kind: 'update', id: state.user.id, input: { is_active: !state.user.isActive } },
        done(state.user.isActive ? `${state.user.displayName} deactivated` : `${state.user.displayName} reactivated`),
      )
    }
  }

  const title = { create: 'New user', edit: 'Edit user', password: 'Set a temporary password', 'reset-mfa': 'Reset multi-factor authentication?', active: user?.isActive ? 'Deactivate account?' : 'Reactivate account?' }[state.kind]
  const description = {
    create: 'They sign in with the temporary password you set here. Give it to them in person or by phone, never by email.',
    edit: 'Changing the role ends their current sessions, so the new permissions apply immediately.',
    password: `${user?.displayName} is signed out everywhere and must use this password next time.`,
    'reset-mfa': `Only for a lost phone with no recovery codes. Check who is asking first (in person or by a known phone number): ${user?.displayName} is signed out and can sign in with just the password until they set MFA up again.`,
    active: user?.isActive
      ? `${user?.displayName} is signed out everywhere and cannot sign in until reactivated. Their work and audit history stay.`
      : `${user?.displayName} will be able to sign in again.`,
  }[state.kind]
  const needsPassword = state.kind === 'create' || state.kind === 'password'

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>{description}</DialogDescription>
        </DialogHeader>
        <form id="user-form" onSubmit={submit} className="space-y-4">
          {state.kind === 'create' && (
            <div className="space-y-1.5">
              <Label htmlFor="user-email">Email</Label>
              <Input id="user-email" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="off" />
            </div>
          )}
          {(state.kind === 'create' || state.kind === 'edit') && (
            <>
              <div className="space-y-1.5">
                <Label htmlFor="user-name">Display name</Label>
                <Input id="user-name" required minLength={2} maxLength={120} value={name} onChange={(e) => setName(e.target.value)} />
              </div>
              <div className="space-y-1.5">
                <Label>Role</Label>
                <Select value={role} onValueChange={(v) => setRole(v as Role)}>
                  <SelectTrigger className="w-full" aria-label="Role"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {Object.entries(roleLabels).map(([value, label]) => <SelectItem key={value} value={value}>{label}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
            </>
          )}
          {needsPassword && (
            <div className="space-y-1.5">
              <Label htmlFor="user-password">Temporary password</Label>
              <Input id="user-password" type="text" required minLength={MIN_PASSWORD} value={password} onChange={(e) => setPassword(e.target.value)}
                autoComplete="new-password" spellCheck={false} />
              <p className="text-xs text-muted-foreground">At least {MIN_PASSWORD} characters. A short phrase is easier to say and harder to guess.</p>
            </div>
          )}
          {error && <p className="text-sm text-destructive" role="alert">{error}</p>}
        </form>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Cancel</Button>
          <Button type="submit" form="user-form" variant={(state.kind === 'active' && user?.isActive) || state.kind === 'reset-mfa' ? 'destructive' : 'default'}
            disabled={admin.isPending || (needsPassword && password.length < MIN_PASSWORD)}>
            {state.kind === 'create' ? 'Create user' : state.kind === 'active' ? (user?.isActive ? 'Deactivate' : 'Reactivate') : state.kind === 'reset-mfa' ? 'Reset MFA' : 'Save'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
