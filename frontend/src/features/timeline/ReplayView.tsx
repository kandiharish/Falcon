/**
 * Incident replay: the case's records played back on a running clock.
 *
 *   clock ──▶  located records appear on the map as their moment arrives (the newest pulses)
 *              moving things (vehicles, phones) leave a trail
 *              every record — calls and payments too — scrolls into the ticker
 *
 * A camera whose clock FALCON found to be wrong can be played with its offset removed, so its
 * footage lines up with network-timed sources. The stored times are never changed.
 */
import { useEffect, useMemo, useState } from 'react'
import { CircleMarker, MapContainer, Polyline, TileLayer, Tooltip, useMap } from 'react-leaflet'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { Clock3, Pause, Play, RotateCcw } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Label } from '@/components/ui/label'
import type { InvestigationEvent } from '@/domain/types'
import { useInsights } from '@/services/queries'
import { IdTag } from '@/design-system/IdTag'
import { eventTypeTerms } from '@/design-system/vocabulary'
import { formatInZone, timeInZone } from '@/lib/time'
import { cn } from '@/lib/utils'
import { categoryColor } from './categories'
import { busiestPeriod } from './periods'

const SPEEDS = [
  { label: '1 min / s', caseSecondsPerSecond: 60 },
  { label: '5 min / s', caseSecondsPerSecond: 300 },
  { label: '15 min / s', caseSecondsPerSecond: 900 },
]
const TICK_MS = 100
const TRAIL_TYPES = new Set(['vehicle', 'device'])

interface Props {
  caseRef: string
  events: InvestigationEvent[]
  timeZone: string
  onSelect: (event: InvestigationEvent) => void
}

interface Placed {
  event: InvestigationEvent
  at: number // the moment it is played: corrected for a known clock error if asked
  corrected: number // seconds removed (0 = played as recorded)
}

export function ReplayView({ caseRef, events, timeZone, onSelect }: Props) {
  const { data: insights } = useInsights(caseRef)
  const drift = useMemo(
    () => new Map((insights?.items ?? []).filter((i) => i.kind === 'clock_drift').map((i) => [String(i.data.evidence), Number(i.data.offset_seconds)])),
    [insights],
  )
  const [fixClocks, setFixClocks] = useState(true)

  const timed: Placed[] = useMemo(() => {
    return events
      .filter((e) => e.occurredAt)
      .map((event) => {
        const offset = fixClocks ? (drift.get(event.evidenceReference) ?? 0) : 0
        return { event, at: new Date(event.occurredAt!).getTime() - offset * 1000, corrected: offset }
      })
      .sort((a, b) => a.at - b.at)
  }, [events, drift, fixClocks])

  // Play the busy part of the case; a lone record days later would mean minutes of nothing.
  const range = useMemo((): [number, number] | null => {
    if (timed.length === 0) return null
    const focus = busiestPeriod(timed.map((p) => ({ ...p.event, occurredAt: new Date(p.at).toISOString() })))
    const [from, to] = focus ?? [timed[0].at, timed[timed.length - 1].at]
    return [from - 60_000, to + 60_000]
  }, [timed])

  const [speed, setSpeed] = useState(SPEEDS[0])
  const [playing, setPlaying] = useState(false)
  const [clock, setClock] = useState<number | null>(null)
  const now = clock ?? range?.[0] ?? 0

  useEffect(() => {
    if (!playing || !range) return
    const timer = setInterval(() => {
      setClock((c) => {
        const next = (c ?? range[0]) + speed.caseSecondsPerSecond * TICK_MS
        if (next >= range[1]) {
          setPlaying(false)
          return range[1]
        }
        return next
      })
    }, TICK_MS)
    return () => clearInterval(timer)
  }, [playing, range, speed])

  if (!range) return <p className="p-6 text-center text-sm text-muted-foreground">No timed events to replay.</p>

  const shown = timed.filter((p) => p.at <= now)
  const located = shown.filter((p) => p.event.latitude !== null && p.event.longitude !== null)
  const newest = shown.at(-1)
  const trails = trailsOf(located)
  const allLocated = timed.filter((p) => p.event.latitude !== null)
  const iso = new Date(now).toISOString()

  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_22rem]">
      <div className="space-y-3">
        <div className="falcon-map relative h-[62svh] min-h-80 overflow-hidden rounded-lg border">
          <MapContainer center={[allLocated[0]?.event.latitude ?? 17.4, allLocated[0]?.event.longitude ?? 78.4]} zoom={14} className="size-full" scrollWheelZoom>
            <TileLayer
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
              url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
              maxZoom={19}
            />
            <FitTo points={allLocated} />
            {trails.map((trail) => (
              <Polyline key={trail.id} positions={trail.points} pathOptions={{ className: 'falcon-path', weight: 3, dashArray: '6 6' }} />
            ))}
            {located.map((p) => {
              const latest = p === newest || p.at === newest?.at
              return (
                <CircleMarker
                  key={p.event.reference}
                  center={[p.event.latitude!, p.event.longitude!]}
                  radius={latest ? 11 : 7}
                  pathOptions={{ color: '#fff', weight: 2, fillColor: resolveColor(categoryColor(p.event)), fillOpacity: latest ? 1 : 0.75, className: latest ? 'falcon-pulse' : '' }}
                  eventHandlers={{ click: () => onSelect(p.event) }}
                >
                  <Tooltip>
                    <strong>{timeInZone(new Date(p.at).toISOString(), timeZone)}</strong> · {eventTypeTerms[p.event.eventType].label}
                    <br />{p.event.description}
                  </Tooltip>
                </CircleMarker>
              )
            })}
          </MapContainer>
          {/* The clock, over the map */}
          <div className="pointer-events-none absolute top-3 right-3 z-[400] rounded-lg border bg-card/90 px-3 py-2 shadow-sm backdrop-blur">
            <p className="flex items-center gap-1.5 text-[0.65rem] tracking-widest text-muted-foreground uppercase"><Clock3 aria-hidden className="size-3" /> Case time</p>
            <p className="font-mono text-2xl font-semibold tabular-nums" aria-live="off">{timeInZone(iso, timeZone)}</p>
            <p className="text-xs text-muted-foreground">{formatInZone(iso, timeZone, { weekday: 'short', day: 'numeric', month: 'short' })}</p>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-3 rounded-lg border bg-card px-3 py-2">
          <Button size="sm" onClick={() => {
            if (!playing && now >= range[1]) setClock(range[0])
            setPlaying((p) => !p)
          }}>
            {playing ? <><Pause /> Pause</> : <><Play /> Play</>}
          </Button>
          <Button variant="outline" size="icon-sm" aria-label="Back to the start" onClick={() => { setPlaying(false); setClock(range[0]) }}><RotateCcw /></Button>
          <input
            type="range" min={range[0]} max={range[1]} step={1000} value={now}
            onChange={(e) => { setPlaying(false); setClock(Number(e.target.value)) }}
            aria-label="Case time" aria-valuetext={timeInZone(iso, timeZone)}
            className="min-w-40 flex-1 accent-primary"
          />
          <div className="flex gap-1" role="group" aria-label="Replay speed">
            {SPEEDS.map((s) => (
              <Button key={s.label} size="xs" variant={s === speed ? 'default' : 'outline'} aria-pressed={s === speed} onClick={() => setSpeed(s)}>{s.label}</Button>
            ))}
          </div>
        </div>
        {drift.size > 0 && (
          <div className="flex items-start gap-2 rounded-lg border border-warning/40 bg-warning/5 px-3 py-2 text-sm">
            <Checkbox id="fix-clocks" checked={fixClocks} onCheckedChange={(v) => setFixClocks(v === true)} className="mt-0.5" />
            <Label htmlFor="fix-clocks" className="block font-normal leading-snug">
              Correct known camera clock errors while replaying:{' '}
              {[...drift].map(([ref, s]) => `${ref} ${s > 0 ? '−' : '+'}${Math.abs(s)} s`).join(', ')}.
              <span className="block text-xs text-muted-foreground">Only the replay is adjusted. The recorded times stay as they are.</span>
            </Label>
          </div>
        )}
      </div>

      <section aria-label="Records so far" className="flex max-h-[calc(62svh+7rem)] flex-col rounded-lg border bg-card">
        <p className="border-b px-3 py-2 text-sm font-medium">
          {shown.length} of {timed.length} records <span className="font-normal text-muted-foreground">so far</span>
        </p>
        <ol className="flex-1 space-y-1 overflow-y-auto p-2">
          {[...shown].reverse().map((p, i) => (
            <li key={p.event.reference}>
              <button type="button" onClick={() => onSelect(p.event)}
                className={cn('w-full rounded-md px-2 py-1.5 text-left text-sm outline-none transition-colors hover:bg-accent focus-visible:ring-2 focus-visible:ring-ring', i === 0 && 'bg-primary/10')}>
                <span className="flex items-center gap-2">
                  <span aria-hidden className="size-2.5 shrink-0 rounded-full" style={{ background: categoryColor(p.event) }} />
                  <span className="font-mono text-xs tabular-nums">{timeInZone(new Date(p.at).toISOString(), timeZone)}</span>
                  <IdTag className="ml-auto">{p.event.evidenceReference}</IdTag>
                </span>
                <span className="mt-0.5 line-clamp-2 block text-muted-foreground">{p.event.description}</span>
                {p.corrected !== 0 && <span className="block text-[0.7rem] text-warning">clock corrected by {Math.abs(p.corrected)} s</span>}
              </button>
            </li>
          ))}
        </ol>
      </section>
    </div>
  )
}

/** Moving things leave a trail: each vehicle's or device's located records, in time order. */
function trailsOf(located: Placed[]) {
  const byEntity = new Map<string, [number, number][]>()
  for (const p of located) {
    for (const who of p.event.participants) {
      if (!TRAIL_TYPES.has(who.entityType)) continue
      const points = byEntity.get(who.reference) ?? []
      points.push([p.event.latitude!, p.event.longitude!])
      byEntity.set(who.reference, points)
    }
  }
  return [...byEntity].filter(([, points]) => points.length > 1).map(([id, points]) => ({ id, points }))
}

function FitTo({ points }: { points: Placed[] }) {
  const map = useMap()
  useEffect(() => {
    const bounds = L.latLngBounds(points.map((p) => [p.event.latitude!, p.event.longitude!] as [number, number]))
    if (bounds.isValid()) map.fitBounds(bounds, { padding: [50, 50], maxZoom: 16 })
  }, [points, map])
  return null
}

/** Leaflet draws SVG paths with attributes, which cannot read CSS variables: resolve them. */
const colorCache = new Map<string, string>()
function resolveColor(value: string): string {
  if (!value.startsWith('var(')) return value
  const cached = colorCache.get(value)
  if (cached) return cached
  const probe = document.createElement('span')
  probe.style.color = value
  document.body.appendChild(probe)
  const resolved = getComputedStyle(probe).color
  probe.remove()
  colorCache.set(value, resolved)
  return resolved
}
