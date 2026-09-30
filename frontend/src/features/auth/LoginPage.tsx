import { useState } from 'react'
import { Controller, useForm } from 'react-hook-form'
import { Navigate, useNavigate, useSearchParams } from 'react-router'
import { zodResolver } from '@hookform/resolvers/zod'
import { Eye, EyeOff, FileLock2, Fingerprint, Lock, ScrollText, ShieldCheck } from 'lucide-react'
import { z } from 'zod'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { AppLoading } from '@/app-shell/AppLoading'
import { ApiError } from '@/services/apiClient'
import { useCurrentUser, useLogin } from '@/services/queries'
import { cn } from '@/lib/utils'

// One schema = the TypeScript type AND the runtime validation rules.
const loginSchema = z.object({
  email: z.email('Enter a valid email address.'),
  password: z.string().min(1, 'Enter your password.'),
  remember: z.boolean(),
})
type LoginForm = z.infer<typeof loginSchema>

/** Only same-site paths are allowed after login (prevents "open redirect" attacks). */
function safeNextPath(next: string | null): string {
  return next && next.startsWith('/') && !next.startsWith('//') ? next : '/'
}

const DEMO_ACCOUNTS = [
  ['admin@falcon.example', 'System Administrator'],
  ['k.iyer@falcon.example', 'Supervisor'],
  ['r.varma@falcon.example', 'Investigation Officer'],
  ['a.kumar@falcon.example', 'Forensic Analyst'],
  ['m.das@falcon.example', 'Evidence Analyst'],
] as const

export function LoginPage() {
  const { data: user, isPending } = useCurrentUser()
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const login = useLogin()
  const [showPassword, setShowPassword] = useState(false)
  const next = safeNextPath(params.get('next'))

  const form = useForm<LoginForm>({
    resolver: zodResolver(loginSchema),
    defaultValues: { email: '', password: '', remember: false },
  })

  if (isPending) return <AppLoading />
  if (user) return <Navigate to={next} replace />

  const onSubmit = form.handleSubmit((values) =>
    login.mutate(values, { onSuccess: () => navigate(next, { replace: true }) }),
  )

  const serverError =
    login.error instanceof ApiError ? login.error.message : login.error ? 'Sign-in failed. Try again.' : null
  const { errors } = form.formState

  return (
    <div className="grid min-h-svh lg:grid-cols-[1.1fr_1fr]">
      {/* Brand panel */}
      <aside className="relative hidden flex-col justify-between overflow-hidden bg-sidebar p-10 text-sidebar-foreground lg:flex">
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0 opacity-40 [background:radial-gradient(60%_50%_at_20%_10%,oklch(0.45_0.12_240/0.35),transparent),radial-gradient(40%_40%_at_90%_90%,oklch(0.6_0.12_215/0.2),transparent)]"
        />
        <div className="relative flex items-center gap-3">
          <FalconLogo />
          <div>
            <p className="text-lg font-semibold tracking-[0.3em] text-sidebar-accent-foreground">FALCON</p>
            <p className="text-xs text-sidebar-foreground/70">Forensic Analysis and Linked Crime Observation Network</p>
          </div>
        </div>
        <div className="relative max-w-md space-y-8">
          <h1 className="text-3xl leading-tight font-semibold text-balance text-sidebar-accent-foreground">
            Connecting Evidence. Revealing Relationships. Supporting Investigation.
          </h1>
          <ul className="space-y-4 text-sm">
            <Feature icon={FileLock2} title="Evidence integrity">
              Originals are fingerprinted and never modified.
            </Feature>
            <Feature icon={Fingerprint} title="Explainable analysis">
              Every relationship shows the evidence behind it.
            </Feature>
            <Feature icon={ScrollText} title="Complete audit trail">
              Every sensitive action is recorded and cannot be edited.
            </Feature>
          </ul>
        </div>
        <p className="relative text-xs text-sidebar-foreground/60">
          Investigation-support platform. Final decisions remain with the investigator.
        </p>
      </aside>

      {/* Sign-in form */}
      <main className="flex items-center justify-center bg-background px-4 py-10">
        <div className="w-full max-w-sm space-y-6">
          <div className="flex items-center gap-2 lg:hidden">
            <FalconLogo />
            <span className="font-semibold tracking-[0.3em]">FALCON</span>
          </div>
          <div className="space-y-1">
            <h2 className="text-xl font-semibold">Sign in</h2>
            <p className="text-sm text-muted-foreground">Use your FALCON account to continue.</p>
          </div>

          <form onSubmit={onSubmit} noValidate className="space-y-4">
            {serverError && (
              <div role="alert" className="rounded-md border border-destructive/25 bg-destructive/5 px-3 py-2 text-sm">
                {serverError}
              </div>
            )}

            <div className="space-y-1.5">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                autoComplete="username"
                autoFocus
                aria-invalid={!!errors.email}
                aria-describedby={errors.email ? 'email-error' : undefined}
                {...form.register('email')}
              />
              {errors.email && (
                <p id="email-error" className="text-xs text-destructive">{errors.email.message}</p>
              )}
            </div>

            <div className="space-y-1.5">
              <div className="flex items-center justify-between">
                <Label htmlFor="password">Password</Label>
                <ForgotPasswordDialog />
              </div>
              <div className="relative">
                <Input
                  id="password"
                  type={showPassword ? 'text' : 'password'}
                  autoComplete="current-password"
                  className="pr-9"
                  aria-invalid={!!errors.password}
                  aria-describedby={errors.password ? 'password-error' : undefined}
                  {...form.register('password')}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((v) => !v)}
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                  aria-pressed={showPassword}
                  className="absolute inset-y-0 right-0 flex w-9 items-center justify-center rounded-r-lg text-muted-foreground outline-none hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring"
                >
                  {showPassword ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
                </button>
              </div>
              {errors.password && (
                <p id="password-error" className="text-xs text-destructive">{errors.password.message}</p>
              )}
            </div>

            <Controller
              control={form.control}
              name="remember"
              render={({ field }) => (
                <div className="flex items-center gap-2">
                  <Checkbox
                    id="remember"
                    checked={field.value}
                    onCheckedChange={(checked) => field.onChange(checked === true)}
                  />
                  <Label htmlFor="remember" className="font-normal">
                    Remember this device for 7 days
                  </Label>
                </div>
              )}
            />

            <Button type="submit" className="w-full" size="lg" disabled={login.isPending}>
              <Lock />
              {login.isPending ? 'Signing in…' : 'Sign in'}
            </Button>
          </form>

          <div className="flex items-start gap-2 rounded-md bg-muted/60 p-3 text-xs text-muted-foreground">
            <ShieldCheck aria-hidden className="mt-0.5 size-4 shrink-0 text-success" />
            <p>
              Authorized personnel only. Sign-ins and activity are recorded in the audit log.
              Multi-factor authentication can be enabled for your account by an administrator.
            </p>
          </div>

          {import.meta.env.DEV && <DemoAccounts onPick={(email) => form.setValue('email', email)} />}
        </div>
      </main>
    </div>
  )
}

function Feature({ icon: Icon, title, children }: { icon: typeof Lock; title: string; children: string }) {
  return (
    <li className="flex gap-3">
      <span className="flex size-8 shrink-0 items-center justify-center rounded-md bg-sidebar-accent">
        <Icon aria-hidden className="size-4 text-sidebar-primary" />
      </span>
      <span>
        <span className="block font-medium text-sidebar-accent-foreground">{title}</span>
        <span className="text-sidebar-foreground/75">{children}</span>
      </span>
    </li>
  )
}

function FalconLogo({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" className={cn('size-9', className)} aria-hidden>
      <rect width="32" height="32" rx="7" className="fill-sidebar-accent" />
      <path d="M6 21 16 8l10 13-10-4z" className="fill-sidebar-primary" />
      <circle cx="16" cy="23" r="2" className="fill-sidebar-accent-foreground" />
    </svg>
  )
}

function ForgotPasswordDialog() {
  return (
    <Dialog>
      <DialogTrigger asChild>
        <button type="button" className="text-xs text-primary underline-offset-4 hover:underline">
          Forgot password?
        </button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Reset your password</DialogTitle>
          <DialogDescription>
            For security, FALCON does not send password-reset links by email. Contact your system
            administrator, who will verify your identity and issue a temporary password.
          </DialogDescription>
        </DialogHeader>
      </DialogContent>
    </Dialog>
  )
}

/** Development only (never built into production): fictional accounts for testing roles. */
function DemoAccounts({ onPick }: { onPick: (email: string) => void }) {
  return (
    <details className="rounded-md border border-dashed p-3 text-xs">
      <summary className="cursor-pointer font-medium">Development demo accounts</summary>
      <p className="mt-2 text-muted-foreground">
        Password: the <code className="font-mono">DEMO_PASSWORD</code> value in your <code className="font-mono">.env</code> file.
      </p>
      <ul className="mt-2 space-y-1">
        {DEMO_ACCOUNTS.map(([email, role]) => (
          <li key={email}>
            <button
              type="button"
              onClick={() => onPick(email)}
              className="w-full rounded px-1.5 py-1 text-left hover:bg-muted"
            >
              <span className="font-mono">{email}</span>
              <span className="text-muted-foreground"> · {role}</span>
            </button>
          </li>
        ))}
      </ul>
    </details>
  )
}
