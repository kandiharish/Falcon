/**
 * A zoomable, pannable, keyboard-accessible timeline (plan §17).
 *
 *   x = (time − viewStart) / (viewEnd − viewStart) × width
 *
 * • Mouse wheel zooms around the pointer; drag pans; buttons zoom/fit.
 * • Each lane is a group (evidence source, event type or entity).
 * • Events close together in a lane stack into sub-rows instead of overlapping.
 * • Every event is a real <button>: Tab to it, Enter to open it.
 */
import { useCallback, useEffect, useMemo, useRef, useState, type PointerEvent } from 'react'
import { Crosshair, Maximize2, ZoomIn, ZoomOut } from 'lucide-react'
import { Button } from '@/components/ui/button'
import type { InvestigationEvent } from '@/domain/types'
import { eventTypeTerms } from '@/design-system/vocabulary'
import { formatInZone, offsetMinutes } from '@/lib/time'
import { cn } from '@/lib/utils'
import { categoryColor } from './categories'
import { busiestPeriod } from './periods'

export interface Lane {
  id: string
  label: string
}

interface Props {
  events: InvestigationEvent[]
  lanes: Lane[]
  laneIdsOf: (event: InvestigationEvent) => string[]
  timeZone: string
  selected: string | null
  onSelect: (event: InvestigationEvent) => void
}

const LABEL_WIDTH = 168
const SUB_ROW = 18
const ROW_PADDING = 10
const MIN_SPAN = 60_000 // never zoom closer than one minute across the whole view
const MAX_SPAN = 5 * 365 * 86_400_000
const DOT = 12

// Tick steps from 1 second to 1 month; the one giving ~1 label per 110 px is used.
const STEPS = [1, 5, 15, 30, 60, 300, 900, 1800, 3600, 3 * 3600, 6 * 3600, 12 * 3600, 86400, 7 * 86400, 30 * 86400].map(
  (s) => s * 1000,
)

export function TimelineChart({ events, lanes, laneIdsOf, timeZone, selected, onSelect }: Props) {
  const timed = useMemo(() => events.filter((e) => e.occurredAt), [events])
  const bounds = useMemo(() => extent(timed), [timed])
  const dataKey = bounds ? `${bounds[0]}-${bounds[1]}` : 'empty'
  // The view is DERIVED: the user's zoom/pan for this data set, otherwise the busiest period
  // (or everything). New filters → new data → back to the default, with no effect needed.
  const [userView, setUserView] = useState<{ dataKey: string; range: [number, number] } | null>(null)
  const fitted = bounds ? pad(bounds) : null
  const focus = useMemo(() => busiestPeriod(timed), [timed])
  const initial = focus ? pad(focus) : fitted
  const view = userView?.dataKey === dataKey ? userView.range : initial
  const [width, setWidth] = useState(800)
  const plotRef = useRef<HTMLDivElement>(null)
  const drag = useRef<{ x: number; view: [number, number] } | null>(null)
  const hasPlot = view !== null && timed.length > 0

  const setView = useCallback((range: [number, number]) => setUserView({ dataKey, range }), [dataKey])

  const zoom = useCallback(
    (factor: number, anchorRatio = 0.5) => {
      if (!view) return
      const [start, end] = view
      const span = clamp((end - start) * factor, MIN_SPAN, MAX_SPAN)
      const anchor = start + (end - start) * anchorRatio
      setView([anchor - span * anchorRatio, anchor + span * (1 - anchorRatio)])
    },
    [view, setView],
  )

  // Wheel = zoom around the pointer. A native listener with passive:false is needed so we can
  // stop the page from scrolling at the same time (React's onWheel cannot prevent that).
  useEffect(() => {
    const element = plotRef.current
    if (!element) return
    const onWheel = (e: globalThis.WheelEvent) => {
      e.preventDefault()
      const rect = element.getBoundingClientRect()
      zoom(e.deltaY > 0 ? 1.25 : 0.8, clamp((e.clientX - rect.left) / rect.width, 0, 1))
    }
    element.addEventListener('wheel', onWheel, { passive: false })
    return () => element.removeEventListener('wheel', onWheel)
  }, [zoom, hasPlot])

  // Track the plot's width so positions stay correct when the window resizes.
  useEffect(() => {
    const element = plotRef.current
    if (!element) return
    const observer = new ResizeObserver(([entry]) => setWidth(Math.max(200, entry.contentRect.width)))
    observer.observe(element)
    return () => observer.disconnect()
  }, [hasPlot]) // the plot only exists once there is something to show

  if (!view || !hasPlot) {
    return <p className="p-6 text-center text-sm text-muted-foreground">No events with a time match these filters.</p>
  }

  const [start, end] = view
  const xOf = (iso: string) => ((new Date(iso).getTime() - start) / (end - start)) * width
  const step = STEPS.find((s) => (width / ((end - start) / s)) >= 110) ?? STEPS[STEPS.length - 1]
  const ticks: number[] = []
  // Align ticks to round LOCAL times (21:00, not 20:30 for a +05:30 zone): shift into the zone,
  // round, shift back.
  const zoneShift = offsetMinutes(timeZone, new Date(start)) * 60_000
  for (let t = Math.ceil((start + zoneShift) / step) * step - zoneShift; t <= end; t += step) ticks.push(t)
  const tickFormat: Intl.DateTimeFormatOptions =
    step < 60_000 ? { hour: '2-digit', minute: '2-digit', second: '2-digit', hourCycle: 'h23' }
      : step < 86_400_000 ? { hour: '2-digit', minute: '2-digit', hourCycle: 'h23' }
        : { day: 'numeric', month: 'short' }

  const rows = lanes.map((lane) => ({ lane, placed: stack(timed.filter((e) => laneIdsOf(e).includes(lane.id)), xOf) }))

  const onPointerDown = (e: PointerEvent<HTMLDivElement>) => {
    if ((e.target as HTMLElement).closest('button')) return
    drag.current = { x: e.clientX, view }
    e.currentTarget.setPointerCapture(e.pointerId)
  }
  const onPointerMove = (e: PointerEvent<HTMLDivElement>) => {
    if (!drag.current) return
    const shift = ((e.clientX - drag.current.x) / width) * (drag.current.view[1] - drag.current.view[0])
    setView([drag.current.view[0] - shift, drag.current.view[1] - shift])
  }

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-muted-foreground">
        <span>
          {formatInZone(new Date(start).toISOString(), timeZone)} — {formatInZone(new Date(end).toISOString(), timeZone)}
        </span>
        <div className="flex gap-1">
          <Button variant="outline" size="icon-sm" aria-label="Zoom in" onClick={() => zoom(0.5)}><ZoomIn /></Button>
          <Button variant="outline" size="icon-sm" aria-label="Zoom out" onClick={() => zoom(2)}><ZoomOut /></Button>
          {focus && (
            <Button variant="outline" size="sm" onClick={() => setView(pad(focus))}><Crosshair /> Busiest period</Button>
          )}
          <Button variant="outline" size="sm" onClick={() => fitted && setView(fitted)}><Maximize2 /> Fit all</Button>
        </div>
      </div>

      <div className="overflow-hidden rounded-lg border bg-card">
        {/* Axis */}
        <div className="flex border-b">
          <div style={{ width: LABEL_WIDTH }} className="shrink-0 border-r px-3 py-1.5 text-xs text-muted-foreground">
            {timeZone}
          </div>
          <div className="relative h-7 flex-1">
            {ticks.map((t) => (
              <span
                key={t}
                className="absolute top-1.5 -translate-x-1/2 font-mono text-[0.68rem] whitespace-nowrap text-muted-foreground tabular-nums"
                style={{ left: ((t - start) / (end - start)) * width }}
              >
                {formatInZone(new Date(t).toISOString(), timeZone, tickFormat)}
              </span>
            ))}
          </div>
        </div>

        {/* Lanes */}
        <div className="flex">
          <div style={{ width: LABEL_WIDTH }} className="shrink-0 border-r">
            {rows.map(({ lane, placed }) => (
              <div key={lane.id} style={{ height: rowHeight(placed) }} className="flex items-center border-b px-3 text-xs font-medium last:border-b-0">
                <span className="truncate" title={lane.label}>{lane.label}</span>
              </div>
            ))}
          </div>
          <div
            ref={plotRef}
            className="relative flex-1 cursor-grab touch-none select-none active:cursor-grabbing"
            onPointerDown={onPointerDown}
            onPointerMove={onPointerMove}
            onPointerUp={() => (drag.current = null)}
            role="group"
            aria-label="Timeline. Scroll to zoom, drag to move."
          >
            {/* Grid lines */}
            {ticks.map((t) => (
              <span key={t} aria-hidden className="absolute inset-y-0 w-px bg-border/60" style={{ left: ((t - start) / (end - start)) * width }} />
            ))}
            {rows.map(({ lane, placed }) => (
              <div key={lane.id} style={{ height: rowHeight(placed) }} className="relative border-b last:border-b-0">
                {placed.map(({ event, x, x2, sub }) => {
                  if (x2 < -DOT || x > width + DOT) return null // outside the visible window
                  const isRange = x2 - x > DOT
                  const label = `${formatInZone(event.occurredAt!, timeZone, { dateStyle: 'medium', timeStyle: 'medium' })}, ${eventTypeTerms[event.eventType].label}: ${event.description}`
                  return (
                    <button
                      key={`${lane.id}-${event.reference}`}
                      type="button"
                      title={label}
                      aria-label={label}
                      aria-pressed={selected === event.reference}
                      onClick={() => onSelect(event)}
                      className={cn(
                        'absolute rounded-full border-2 border-card outline-none transition-transform hover:scale-125 focus-visible:ring-2 focus-visible:ring-ring',
                        selected === event.reference && 'ring-2 ring-foreground',
                        event.reviewStatus === 'rejected' && 'opacity-40',
                      )}
                      style={{
                        left: isRange ? x : x - DOT / 2,
                        width: isRange ? x2 - x : DOT,
                        top: ROW_PADDING / 2 + sub * SUB_ROW + (SUB_ROW - DOT) / 2,
                        height: DOT,
                        // Analyst observations are hollow rings; automatic results are filled dots.
                        ...(event.assertionKind === 'user_entered'
                          ? { background: 'var(--card)', borderColor: categoryColor(event), borderWidth: 3 }
                          : { background: categoryColor(event) }),
                      }}
                    />
                  )
                })}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}

interface Placed {
  event: InvestigationEvent
  x: number
  x2: number
  sub: number
}

/** Greedy stacking: put each item in the first sub-row where it doesn't overlap. */
function stack(events: InvestigationEvent[], xOf: (iso: string) => number): Placed[] {
  const sorted = [...events].sort((a, b) => a.occurredAt!.localeCompare(b.occurredAt!))
  const rowEnds: number[] = []
  return sorted.map((event) => {
    const x = xOf(event.occurredAt!)
    const x2 = Math.max(x, event.endedAt ? xOf(event.endedAt) : x)
    let sub = rowEnds.findIndex((endX) => x - endX > DOT + 2)
    if (sub === -1) {
      sub = rowEnds.length
      rowEnds.push(x2)
    } else rowEnds[sub] = x2
    return { event, x, x2, sub }
  })
}

const rowHeight = (placed: Placed[]) => ROW_PADDING + SUB_ROW * Math.max(1, ...placed.map((p) => p.sub + 1))

function extent(events: InvestigationEvent[]): [number, number] | null {
  if (events.length === 0) return null
  const times = events.flatMap((e) => [new Date(e.occurredAt!).getTime(), e.endedAt ? new Date(e.endedAt).getTime() : NaN]).filter(Number.isFinite)
  return [Math.min(...times), Math.max(...times)]
}

function pad([start, end]: [number, number]): [number, number] {
  const span = Math.max(end - start, MIN_SPAN * 10)
  const middle = (start + end) / 2
  return [middle - span * 0.55, middle + span * 0.55]
}

const clamp = (value: number, low: number, high: number) => Math.min(high, Math.max(low, value))
