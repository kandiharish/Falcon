import { useState } from 'react'
import { ChevronLeft, ChevronRight, Download, ScrollText, ShieldCheck } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from '@/components/ui/sheet'
import { Skeleton } from '@/components/ui/skeleton'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import type { AuditEntry } from '@/domain/types'
import { ApiError } from '@/services/apiClient'
import { auditQueryString, type AuditQuery } from '@/services/adminService'
import { useAuditLog } from '@/services/queries'
import { PageHeader } from '@/design-system/PageHeader'
import { EmptyState, ErrorState } from '@/design-system/states'
import { auditActionLabels } from '@/design-system/vocabulary'
import { formatDateTime } from '@/lib/format'

const PAGE = 50
const ALL = 'all'
const AREAS: { value: string; label: string }[] = [
  { value: 'auth.', label: 'Sign-in and sessions' },
  { value: 'user.', label: 'User management' },
  { value: 'investigation.', label: 'Investigations' },
  { value: 'evidence.', label: 'Evidence' },
  { value: 'entity.', label: 'Entities' },
  { value: 'event.', label: 'Events' },
  { value: 'correlation.', label: 'Correlations' },
  { value: 'task.', label: 'Tasks' },
  { value: 'report.', label: 'Reports' },
  { value: 'ai.', label: 'AI search and index' },
  { value: 'assistant.', label: 'Investigation Assistant' },
  { value: 'audit.', label: 'Audit exports' },
]

/** Audit logs (plan §25): who did what, when, to what, and what changed. Read-only by design. */
export function AuditPage() {
  const [area, setArea] = useState(ALL)
  const [actor, setActor] = useState('')
  const [object, setObject] = useState('')
  const [from, setFrom] = useState('')
  const [to, setTo] = useState('')
  const [offset, setOffset] = useState(0)
  const [open, setOpen] = useState<AuditEntry | null>(null)
  const filters: AuditQuery = {
    action: area === ALL ? undefined : area,
    actor: actor.trim() || undefined,
    object: object.trim() || undefined,
    date_from: from || undefined,
    date_to: to || undefined,
  }
  const { data, isPending, isError, error, refetch, isFetching } = useAuditLog({ ...filters, limit: PAGE, offset })
  const change = (set: (v: string) => void) => (value: string) => {
    set(value)
    setOffset(0)
  }

  return (
    <div className="mx-auto max-w-7xl space-y-5">
      <PageHeader
        eyebrow="Governance"
        title="Audit logs"
        description="Every sensitive action, with who did it, when, from where, and what changed. Entries cannot be edited or deleted: the database itself refuses."
        actions={
          <Button variant="outline" asChild>
            <a href={`/api/audit/export.csv${auditQueryString(filters)}`} download><Download /> Export CSV</a>
          </Button>
        }
      />

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
        <div className="space-y-1">
          <Label>Area</Label>
          <Select value={area} onValueChange={change(setArea)}>
            <SelectTrigger className="w-full" aria-label="Area"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL}>Everything</SelectItem>
              {AREAS.map((a) => <SelectItem key={a.value} value={a.value}>{a.label}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-1">
          <Label htmlFor="audit-actor">Who</Label>
          <Input id="audit-actor" value={actor} onChange={(e) => change(setActor)(e.target.value)} placeholder="email…" />
        </div>
        <div className="space-y-1">
          <Label htmlFor="audit-object">What</Label>
          <Input id="audit-object" value={object} onChange={(e) => change(setObject)(e.target.value)} placeholder="CASE-2026-001, CCTV-001…" />
        </div>
        <div className="space-y-1">
          <Label htmlFor="audit-from">From</Label>
          <Input id="audit-from" type="date" value={from} onChange={(e) => change(setFrom)(e.target.value)} />
        </div>
        <div className="space-y-1">
          <Label htmlFor="audit-to">To</Label>
          <Input id="audit-to" type="date" value={to} onChange={(e) => change(setTo)(e.target.value)} />
        </div>
      </div>

      {isError ? (
        <ErrorState description={error instanceof ApiError ? error.message : 'The audit log could not be loaded.'} onRetry={() => refetch()} retrying={isFetching} />
      ) : isPending ? (
        <Skeleton className="h-96 w-full" />
      ) : data.total === 0 ? (
        <EmptyState icon={ScrollText} title="No entries" description="Nothing matches these filters." />
      ) : (
        <Card className="gap-0 py-0">
          <CardContent className="px-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="pl-4">When</TableHead>
                  <TableHead>Who</TableHead>
                  <TableHead>Action</TableHead>
                  <TableHead>What</TableHead>
                  <TableHead className="hidden pr-4 lg:table-cell">From</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.items.map((entry) => (
                  <TableRow key={entry.id} className="cursor-pointer" onClick={() => setOpen(entry)}>
                    <TableCell className="pl-4 whitespace-nowrap tabular-nums">{formatDateTime(entry.occurredAt)}</TableCell>
                    <TableCell className="max-w-48 truncate">{entry.actorEmail ?? 'system'}</TableCell>
                    <TableCell>
                      <button type="button" className="text-left text-primary underline-offset-4 hover:underline focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none" onClick={(e) => { e.stopPropagation(); setOpen(entry) }}>
                        {auditActionLabels[entry.action] ?? entry.action}
                      </button>
                    </TableCell>
                    <TableCell className="max-w-64 truncate font-mono text-xs">{entry.objectId ?? ''}</TableCell>
                    <TableCell className="hidden pr-4 font-mono text-xs text-muted-foreground lg:table-cell">{entry.ipAddress ?? ''}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
            <div className="flex items-center justify-between border-t px-4 py-2 text-sm text-muted-foreground">
              <span>{offset + 1}–{Math.min(offset + PAGE, data.total)} of {data.total.toLocaleString()}</span>
              <div className="flex gap-1">
                <Button variant="ghost" size="sm" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE))}><ChevronLeft /> Newer</Button>
                <Button variant="ghost" size="sm" disabled={offset + PAGE >= data.total} onClick={() => setOffset(offset + PAGE)}>Older <ChevronRight /></Button>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      <Sheet open={open !== null} onOpenChange={(value) => !value && setOpen(null)}>
        <SheetContent className="w-full overflow-y-auto sm:max-w-lg">
          {open && (
            <>
              <SheetHeader>
                <SheetTitle>{auditActionLabels[open.action] ?? open.action}</SheetTitle>
                <SheetDescription className="font-mono text-xs">#{open.id} · {open.action}</SheetDescription>
              </SheetHeader>
              <div className="space-y-4 px-4 pb-6 text-sm">
                <dl className="grid grid-cols-[6rem_1fr] gap-y-1.5">
                  <dt className="text-muted-foreground">When</dt><dd>{formatDateTime(open.occurredAt)}</dd>
                  <dt className="text-muted-foreground">Who</dt><dd>{open.actorEmail ?? 'system'}</dd>
                  <dt className="text-muted-foreground">What</dt><dd className="font-mono text-xs break-all">{open.objectType ? `${open.objectType} · ` : ''}{open.objectId ?? 'n/a'}</dd>
                  <dt className="text-muted-foreground">From</dt><dd className="font-mono text-xs">{open.ipAddress ?? 'n/a'}</dd>
                  {open.note && (<><dt className="text-muted-foreground">Note</dt><dd>{open.note}</dd></>)}
                </dl>
                <StateBlock title="Before" state={open.previousState} />
                <StateBlock title="After" state={open.newState} />
                <p className="flex items-start gap-2 text-xs text-muted-foreground">
                  <ShieldCheck aria-hidden className="mt-0.5 size-4 shrink-0" /> Append-only: a database trigger rejects any change or deletion of audit entries.
                </p>
              </div>
            </>
          )}
        </SheetContent>
      </Sheet>
    </div>
  )
}

function StateBlock({ title, state }: { title: string; state: Record<string, unknown> | null }) {
  if (!state) return null
  return (
    <div className="space-y-1">
      <p className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">{title}</p>
      <pre className="rounded-md border bg-muted/40 p-3 font-mono text-xs whitespace-pre-wrap [overflow-wrap:anywhere]">{JSON.stringify(state, null, 2)}</pre>
    </div>
  )
}
