import { useState } from 'react'
import { Copy, Download, KeyRound, Laptop, LogOut, ShieldCheck, ShieldOff, Smartphone } from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Skeleton } from '@/components/ui/skeleton'
import { ApiError } from '@/services/apiClient'
import { AuthService } from '@/services/authService'
import { queryClient, useCurrentUser, useEndSession, useSessions } from '@/services/queries'
import { PageHeader } from '@/design-system/PageHeader'
import { formatDateTime, timeAgo } from '@/lib/format'

const message = (error: unknown, fallback: string) => (error instanceof ApiError ? error.message : fallback)
const refreshMe = () => queryClient.invalidateQueries({ queryKey: ['auth', 'me'] })

/** Your account: multi-factor authentication and where you are signed in (plan §26). */
export function SecurityPage() {
  const { data: user } = useCurrentUser()
  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <PageHeader eyebrow="Your account" title="Account security" description={`Signed in as ${user?.email ?? ''}.`} />
      {user?.mfaEnabled ? <MfaOn /> : <MfaSetup />}
      <Sessions />
    </div>
  )
}

function MfaSetup() {
  const [setup, setSetup] = useState<{ secret: string; qr_svg: string } | null>(null)
  const [code, setCode] = useState('')
  const [recovery, setRecovery] = useState<string[] | null>(null)
  const [busy, setBusy] = useState(false)

  const start = async () => {
    setBusy(true)
    try {
      setSetup(await AuthService.mfaSetup())
    } catch (error) {
      toast.error('Could not start the set-up', { description: message(error, '') })
    } finally {
      setBusy(false)
    }
  }
  const confirm = async (event: React.FormEvent) => {
    event.preventDefault()
    setBusy(true)
    try {
      setRecovery((await AuthService.mfaConfirm(code.trim())).recovery_codes)
    } catch (error) {
      toast.error(message(error, 'That code is not right.'))
    } finally {
      setBusy(false)
    }
  }

  if (recovery) return <RecoveryCodes codes={recovery} onDone={refreshMe} />

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2"><ShieldOff aria-hidden className="size-5 text-warning" /> Multi-factor authentication is off</CardTitle>
        <CardDescription>
          With it on, signing in needs your password <em>and</em> a 6-digit code from an app on your phone, so a stolen password alone is not enough.
          Works with any authenticator app (Google Authenticator, Microsoft Authenticator, Aegis, 1Password…).
        </CardDescription>
      </CardHeader>
      <CardContent>
        {!setup ? (
          <Button onClick={start} disabled={busy}><Smartphone /> Set up</Button>
        ) : (
          <form onSubmit={confirm} className="grid gap-6 sm:grid-cols-[auto_1fr]">
            <img src={setup.qr_svg} alt="QR code to add FALCON to your authenticator app" className="size-48 rounded-md bg-white p-1" />
            <div className="space-y-4">
              <ol className="list-decimal space-y-1 pl-5 text-sm">
                <li>In your authenticator app, add an account and scan this QR code.</li>
                <li>Can't scan? Type this key instead: <code className="font-mono text-xs">{setup.secret.match(/.{1,4}/g)?.join(' ')}</code></li>
                <li>Type the 6-digit code the app shows.</li>
              </ol>
              <div className="space-y-1.5">
                <Label htmlFor="setup-code">Code from the app</Label>
                <Input id="setup-code" value={code} onChange={(e) => setCode(e.target.value)} autoComplete="one-time-code" inputMode="numeric"
                  maxLength={7} placeholder="123456" className="w-40 font-mono text-lg tracking-[0.3em]" />
              </div>
              <Button type="submit" disabled={busy || code.replace(/\D/g, '').length !== 6}><ShieldCheck /> Turn on</Button>
            </div>
          </form>
        )}
      </CardContent>
    </Card>
  )
}

function RecoveryCodes({ codes, onDone }: { codes: string[]; onDone: () => void }) {
  const text = `FALCON recovery codes. Each works once, if you lose your phone.\n\n${codes.join('\n')}\n`
  const download = () => {
    const url = URL.createObjectURL(new Blob([text], { type: 'text/plain' }))
    const link = Object.assign(document.createElement('a'), { href: url, download: 'falcon-recovery-codes.txt' })
    link.click()
    URL.revokeObjectURL(url)
  }
  return (
    <Card className="border-success/40">
      <CardHeader>
        <CardTitle className="flex items-center gap-2"><ShieldCheck aria-hidden className="size-5 text-success" /> Multi-factor authentication is on</CardTitle>
        <CardDescription>
          Save these recovery codes somewhere safe, away from your phone. Each one signs you in once if the phone is lost. <strong>They will not be shown again.</strong>
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <ul className="grid grid-cols-2 gap-2 rounded-md border bg-muted/40 p-4 font-mono text-sm sm:grid-cols-4">
          {codes.map((c) => <li key={c}>{c}</li>)}
        </ul>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" onClick={() => navigator.clipboard.writeText(codes.join('\n')).then(() => toast.success('Copied'))}><Copy /> Copy</Button>
          <Button variant="outline" onClick={download}><Download /> Download .txt</Button>
          <Button onClick={onDone}>I have saved them</Button>
        </div>
      </CardContent>
    </Card>
  )
}

function MfaOn() {
  const [password, setPassword] = useState('')
  const [code, setCode] = useState('')
  const [busy, setBusy] = useState(false)
  const turnOff = async (event: React.FormEvent) => {
    event.preventDefault()
    setBusy(true)
    try {
      await AuthService.mfaDisable(password, code.trim())
      toast.success('Multi-factor authentication turned off')
      await refreshMe()
    } catch (error) {
      toast.error(message(error, 'Could not turn it off.'))
    } finally {
      setBusy(false)
    }
  }
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2"><ShieldCheck aria-hidden className="size-5 text-success" /> Multi-factor authentication is on</CardTitle>
        <CardDescription>Signing in needs your password and a code from your authenticator app.</CardDescription>
      </CardHeader>
      <CardContent>
        <details>
          <summary className="cursor-pointer text-sm font-medium">Turn it off…</summary>
          <form onSubmit={turnOff} className="mt-3 grid gap-3 sm:grid-cols-[1fr_10rem_auto] sm:items-end">
            <div className="space-y-1.5">
              <Label htmlFor="off-password">Password</Label>
              <Input id="off-password" type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="off-code">Code</Label>
              <Input id="off-code" value={code} onChange={(e) => setCode(e.target.value)} autoComplete="one-time-code" maxLength={20} className="font-mono" />
            </div>
            <Button type="submit" variant="destructive" disabled={busy || !password || code.trim().length < 6}>Turn off</Button>
          </form>
        </details>
      </CardContent>
    </Card>
  )
}

function device(userAgent: string | null): { label: string; icon: typeof Laptop } {
  const ua = userAgent ?? ''
  const browser = /Edg\//.test(ua) ? 'Edge' : /Chrome\//.test(ua) ? 'Chrome' : /Firefox\//.test(ua) ? 'Firefox' : /Safari\//.test(ua) ? 'Safari' : 'Browser'
  const system = /Windows/.test(ua) ? 'Windows' : /Android/.test(ua) ? 'Android' : /iPhone|iPad/.test(ua) ? 'iOS' : /Mac OS/.test(ua) ? 'macOS' : /Linux/.test(ua) ? 'Linux' : ''
  return { label: ua ? `${browser}${system ? ` on ${system}` : ''}` : 'Unknown device', icon: /Android|iPhone/.test(ua) ? Smartphone : Laptop }
}

function Sessions() {
  const { data, isPending } = useSessions()
  const end = useEndSession()
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2"><KeyRound aria-hidden className="size-5" /> Where you are signed in</CardTitle>
        <CardDescription>Sign out anything you do not recognise, then change your password.</CardDescription>
      </CardHeader>
      <CardContent>
        {isPending ? <Skeleton className="h-24 w-full" /> : (
          <ul className="divide-y">
            {data?.map((s) => {
              const d = device(s.userAgent)
              return (
                <li key={s.id} className="flex flex-wrap items-center gap-3 py-3 text-sm">
                  <d.icon aria-hidden className="size-5 text-muted-foreground" />
                  <div className="min-w-0 flex-1">
                    <p className="font-medium">{d.label} {s.current && <span className="ml-1 rounded bg-success/15 px-1.5 py-0.5 text-xs text-success">this device</span>}</p>
                    <p className="text-xs text-muted-foreground">
                      {s.ipAddress ?? 'unknown address'} · active {timeAgo(s.lastSeenAt)} · signed in {formatDateTime(s.createdAt)}
                    </p>
                  </div>
                  {!s.current && (
                    <Button variant="outline" size="sm" disabled={end.isPending}
                      onClick={() => end.mutate(s.id, { onSuccess: () => toast.success('Signed out on that device') })}>
                      <LogOut /> Sign out
                    </Button>
                  )}
                </li>
              )
            })}
          </ul>
        )}
      </CardContent>
    </Card>
  )
}
