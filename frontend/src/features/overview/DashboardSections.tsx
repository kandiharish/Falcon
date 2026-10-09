/**
 * Command-center sections (plan §9). Every number is a count of real records and links to
 * where they are; every chart also says its numbers in words (screen readers, plan §36).
 */
import type { ReactNode } from 'react'
import { Link } from 'react-router'
import {
  Activity,
  CircleAlert,
  FileStack,
  FolderSearch,
  ListChecks,
  Loader,
  ScanSearch,
  TriangleAlert,
  UserRoundSearch,
  Waypoints,
  type LucideIcon,
} from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import type { DashboardDto } from '@/api/types'
import type { EvidenceStatus } from '@/domain/types'
import { StatusBadge } from '@/design-system/badges'
import { toneFillClass, type Tone } from '@/design-system/tones'
import { auditActionLabels } from '@/design-system/vocabulary'
import { formatDay, timeAgo } from '@/lib/format'
import { cn } from '@/lib/utils'
import { useInvestigationContext } from '@/app/investigation-context'

type Data = DashboardDto

const METRICS: { key: string; label: string; icon: LucideIcon; to: string; tone?: Tone }[] = [
  { key: 'active_investigations', label: 'Active cases', icon: FolderSearch, to: '/investigations' },
  { key: 'evidence_items', label: 'Evidence items', icon: FileStack, to: '/evidence' },
  { key: 'evidence_processing', label: 'Processing', icon: Loader, to: '/evidence' },
  { key: 'entities', label: 'Entities', icon: UserRoundSearch, to: '/entities' },
  { key: 'events', label: 'Events', icon: Activity, to: '/events' },
  { key: 'correlations', label: 'Relationships', icon: Waypoints, to: '/correlations' },
  { key: 'requires_review', label: 'To review', icon: ScanSearch, to: '/correlations', tone: 'warning' },
  { key: 'open_tasks', label: 'Open tasks', icon: ListChecks, to: '/tasks' },
]

/** One instrument strip, not eight cards (plan §46): label, number, a link to the records. */
export function MetricTiles({ metrics }: { metrics: Record<string, number> }) {
  return (
    <div className="grid grid-cols-2 gap-px overflow-hidden rounded-lg border bg-border sm:grid-cols-4 xl:grid-cols-8">
      {METRICS.map((m) => {
        const value = metrics[m.key] ?? 0
        const warn = m.tone === 'warning' && value > 0
        return (
          <Link key={m.key} to={m.to}
            className="group relative bg-card px-3 py-2.5 outline-none transition-colors hover:bg-accent/40 focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-inset">
            <p className="flex items-center gap-1.5 truncate text-[0.7rem] text-muted-foreground">
              <m.icon aria-hidden className="size-3.5 shrink-0" /> {m.label}
            </p>
            <p className={cn('mt-0.5 text-xl font-semibold tabular-nums', warn && 'text-warning')}>
              {value.toLocaleString()}
            </p>
            <span aria-hidden className={cn('absolute inset-x-0 bottom-0 h-0.5 scale-x-0 transition-transform group-hover:scale-x-100', warn ? 'bg-warning' : 'bg-primary')} />
          </Link>
        )
      })}
    </div>
  )
}

export function Panel({ title, description, children, className, action }: { title: string; description?: string; children: ReactNode; className?: string; action?: ReactNode }) {
  return (
    <Card className={cn('gap-3', className)}>
      <CardHeader className="flex flex-row items-start justify-between gap-2">
        <div className="space-y-1">
          <CardTitle className="text-base">{title}</CardTitle>
          {description && <CardDescription>{description}</CardDescription>}
        </div>
        {action}
      </CardHeader>
      <CardContent>{children}</CardContent>
    </Card>
  )
}

/** Horizontal bars: label · bar · number. */
export function BarList({ items, tone = 'info', empty }: { items: { label: string; value: number; to?: string }[]; tone?: Tone; empty: string }) {
  const max = Math.max(1, ...items.map((i) => i.value))
  if (items.length === 0) return <p className="text-sm text-muted-foreground">{empty}</p>
  return (
    <ul className="space-y-2">
      {items.map((item) => (
        <li key={item.label} className="grid grid-cols-[minmax(0,9rem)_1fr_2.5rem] items-center gap-2 text-sm">
          <span className="truncate" title={item.label}>{item.label}</span>
          <span className="h-2 overflow-hidden rounded-full bg-muted" aria-hidden>
            <span className={cn('block h-full rounded-full', toneFillClass[tone])} style={{ width: `${(item.value / max) * 100}%` }} />
          </span>
          <span className="text-right font-mono text-xs tabular-nums">{item.value}</span>
        </li>
      ))}
    </ul>
  )
}

/** Columns over time, with the busiest moment named in words. */
export function ColumnChart({ buckets, unit, label }: { buckets: { start: string; count: number }[]; unit: 'hour' | 'day'; label: string }) {
  if (buckets.length === 0) return <p className="text-sm text-muted-foreground">No dated events yet.</p>
  const max = Math.max(1, ...buckets.map((b) => b.count))
  const total = buckets.reduce((sum, b) => sum + b.count, 0)
  const fmt = (iso: string) =>
    new Date(iso).toLocaleString(undefined, unit === 'hour' ? { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' } : { day: 'numeric', month: 'short' })
  const peak = buckets.reduce((a, b) => (b.count > a.count ? b : a))
  return (
    <figure className="space-y-2">
      <div className="flex h-32 items-end gap-0.5" role="img" aria-label={`${label}: ${total} in total, busiest ${fmt(peak.start)} with ${peak.count}.`}>
        {buckets.map((b) => (
          <div key={b.start} className="group relative flex h-full flex-1 items-end" title={`${fmt(b.start)}: ${b.count}`}>
            <div className={cn('w-full rounded-t-sm', b.count ? 'bg-primary/80 group-hover:bg-primary' : 'bg-muted')} style={{ height: `${Math.max(b.count ? 6 : 2, (b.count / max) * 100)}%` }} />
          </div>
        ))}
      </div>
      <figcaption className="flex justify-between text-xs text-muted-foreground">
        <span>{fmt(buckets[0].start)}</span>
        <span>busiest: {fmt(peak.start)} ({peak.count})</span>
        <span>{fmt(buckets[buckets.length - 1].start)}</span>
      </figcaption>
    </figure>
  )
}

export function AlertsList({ alerts }: { alerts: Data['alerts'] }) {
  if (alerts.length === 0) return <p className="text-sm text-muted-foreground">Nothing needs urgent attention.</p>
  return (
    <ul className="space-y-2">
      {alerts.map((a) => (
        <li key={a.title}>
          <Link to={a.link} className={cn('flex items-start gap-2 rounded-md border px-2.5 py-2 text-sm hover:bg-accent', a.tone === 'danger' ? 'border-destructive/40' : 'border-warning/40')}>
            {a.tone === 'danger' ? <CircleAlert aria-hidden className="mt-0.5 size-4 shrink-0 text-destructive" /> : <TriangleAlert aria-hidden className="mt-0.5 size-4 shrink-0 text-warning" />}
            {a.title}
          </Link>
        </li>
      ))}
    </ul>
  )
}

export function PendingReviews({ items }: { items: Data['pending_correlations'] }) {
  const setCase = useInvestigationContext((s) => s.setCurrentInvestigation)
  if (items.length === 0) return <p className="text-sm text-muted-foreground">No potential relationships waiting for review.</p>
  return (
    <ul className="divide-y">
      {items.map((c) => (
        <li key={`${c.investigation_reference}-${c.reference}`} className="py-2 text-sm">
          <Link to={`/investigations/${c.investigation_reference}/correlations/${c.reference}`} onClick={() => setCase(c.investigation_reference)} className="flex items-center gap-2 hover:underline">
            <span className="shrink-0 font-mono text-xs whitespace-nowrap">{c.reference}</span>
            <span className="min-w-0 truncate">{c.evidence_a} ⟷ {c.evidence_b}</span>
            <span className={cn('ml-auto shrink-0 text-xs font-medium whitespace-nowrap', c.level === 'high' ? 'text-success' : c.level === 'medium' ? 'text-warning' : 'text-muted-foreground')}>
              {c.level} {c.score.toFixed(2)}
            </span>
          </Link>
        </li>
      ))}
    </ul>
  )
}

export function MyTasks({ items }: { items: Data['my_tasks'] }) {
  if (items.length === 0) return <p className="text-sm text-muted-foreground">No open tasks assigned to you.</p>
  return (
    <ul className="divide-y">
      {items.map((t) => (
        <li key={`${t.investigation_reference}-${t.reference}`} className="py-2 text-sm">
          <Link to={`/tasks?case=${t.investigation_reference}&task=${t.reference}`} className="block hover:underline">
            <span className="font-mono text-xs text-muted-foreground">{t.reference} · {t.investigation_reference}</span>
            <span className="block truncate">{t.title}</span>
          </Link>
          <span className="text-xs text-muted-foreground">{t.status.replace('_', ' ')}{t.due_date ? ` · due ${formatDay(t.due_date)}` : ''}</span>
        </li>
      ))}
    </ul>
  )
}

export function RecentEvidence({ items }: { items: Data['recent_evidence'] }) {
  if (items.length === 0) return <p className="text-sm text-muted-foreground">No evidence uploaded yet.</p>
  return (
    <ul className="divide-y">
      {items.map((e) => (
        <li key={`${e.investigation_reference}-${e.reference}`} className="flex items-center gap-2 py-2 text-sm">
          <Link to={`/investigations/${e.investigation_reference}/evidence/${e.reference}`} className="min-w-0 flex-1 hover:underline">
            <span className="block font-mono text-xs">{e.reference}</span>
            <span className="block truncate text-muted-foreground">{e.description}</span>
          </Link>
          <StatusBadge kind="evidence" status={e.status as EvidenceStatus} />
        </li>
      ))}
    </ul>
  )
}

export function ActivityFeed({ entries, days }: { entries: Data['activity']; days: Data['activity_by_day'] }) {
  return (
    <div className="space-y-4">
      <ColumnChart buckets={days} unit="day" label="Audit-logged actions per day, last 14 days" />
      <ul className="space-y-1.5 text-sm">
        {entries.map((a) => (
          <li key={a.id} className="flex gap-2">
            <span className="w-16 shrink-0 text-xs text-muted-foreground">{timeAgo(a.occurred_at)}</span>
            <span className="min-w-0">
              {auditActionLabels[a.action] ?? a.action}{' '}
              <span className="font-mono text-xs break-all text-muted-foreground">{a.object_id?.split('/').pop()}</span>
              <span className="block truncate text-xs text-muted-foreground">{a.actor_email ?? 'system'}</span>
            </span>
          </li>
        ))}
      </ul>
    </div>
  )
}
