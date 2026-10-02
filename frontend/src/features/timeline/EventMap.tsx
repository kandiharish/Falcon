/**
 * Map of located events (plan §54) on OpenStreetMap — free, no API key.
 *
 * • Nearby events cluster into a numbered bubble; zoom in to separate them.
 * • Choose an entity to draw its movement: its located events joined in time order.
 * • The time slider replays the case: only events up to the chosen moment are shown.
 */
import { useEffect, useMemo, useRef, useState } from 'react'
import { MapContainer, Polyline, TileLayer, useMap } from 'react-leaflet'
import L from 'leaflet'
import 'leaflet.markercluster'
import 'leaflet/dist/leaflet.css'
import 'leaflet.markercluster/dist/MarkerCluster.css'
import 'leaflet.markercluster/dist/MarkerCluster.Default.css'
import { Pause, Play } from 'lucide-react'
import { Button } from '@/components/ui/button'
import type { InvestigationEvent } from '@/domain/types'
import { eventTypeTerms } from '@/design-system/vocabulary'
import { formatInZone, timeInZone } from '@/lib/time'
import { categoryColor } from './categories'

interface Props {
  events: InvestigationEvent[]
  timeZone: string
  pathEntity: string | null // draw this entity's movement
  onSelect: (event: InvestigationEvent) => void
}

export function EventMap({ events, timeZone, pathEntity, onSelect }: Props) {
  const located = useMemo(
    () =>
      events
        .filter((e) => e.latitude !== null && e.longitude !== null)
        .sort((a, b) => (a.occurredAt ?? '').localeCompare(b.occurredAt ?? '')),
    [events],
  )
  const times = useMemo(
    () => [...new Set(located.filter((e) => e.occurredAt).map((e) => e.occurredAt as string))].sort(),
    [located],
  )
  const [cursor, setCursor] = useState(Number.MAX_SAFE_INTEGER) // index into `times`
  const [playing, setPlaying] = useState(false)
  const lastIndex = times.length - 1
  const index = Math.min(cursor, lastIndex)
  const until = index >= 0 ? times[index] : null

  // Replay: step through the case one moment at a time.
  useEffect(() => {
    if (!playing) return
    const timer = setInterval(() => {
      setCursor((c) => {
        if (Math.min(c, lastIndex) >= lastIndex) {
          setPlaying(false)
          return c
        }
        return Math.min(c, lastIndex) + 1
      })
    }, 700)
    return () => clearInterval(timer)
  }, [playing, lastIndex])

  const visible = until ? located.filter((e) => !e.occurredAt || e.occurredAt <= until) : located
  const path = pathEntity
    ? visible
        .filter((e) => e.occurredAt && e.participants.some((p) => p.reference === pathEntity))
        .map((e) => [e.latitude, e.longitude] as [number, number])
    : []

  if (located.length === 0) {
    return <p className="p-6 text-center text-sm text-muted-foreground">No events with a location match these filters.</p>
  }

  return (
    <div className="space-y-3">
      <div className="falcon-map h-[60svh] min-h-80 overflow-hidden rounded-lg border">
        <MapContainer center={[located[0].latitude!, located[0].longitude!]} zoom={14} className="size-full" scrollWheelZoom>
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
            url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
            maxZoom={19}
          />
          <FitToEvents events={located} />
          <ClusteredMarkers events={visible} timeZone={timeZone} onSelect={onSelect} />
          {path.length > 1 && (
            // Colour comes from CSS (.falcon-path): SVG attributes cannot use CSS variables.
            <Polyline positions={path} pathOptions={{ className: 'falcon-path', weight: 3, dashArray: '6 6' }} />
          )}
        </MapContainer>
      </div>

      {times.length > 1 && (
        <div className="flex flex-wrap items-center gap-3 rounded-lg border bg-card px-3 py-2">
          <Button
            variant="outline"
            size="icon-sm"
            aria-label={playing ? 'Pause replay' : 'Replay events in time order'}
            onClick={() => {
              if (!playing && index >= lastIndex) setCursor(0)
              setPlaying((p) => !p)
            }}
          >
            {playing ? <Pause /> : <Play />}
          </Button>
          <input
            type="range"
            min={0}
            max={lastIndex}
            value={index}
            onChange={(e) => {
              setPlaying(false)
              setCursor(Number(e.target.value))
            }}
            aria-label="Show events up to this time"
            className="min-w-40 flex-1 accent-primary"
          />
          <span className="font-mono text-xs tabular-nums">
            up to {until ? formatInZone(until, timeZone, { dateStyle: 'medium', timeStyle: 'medium' }) : '—'}
          </span>
          <span className="text-xs text-muted-foreground">{visible.length} of {located.length} located events</span>
        </div>
      )}
    </div>
  )
}

/** Zoom the map to show all located events whenever the set changes. */
function FitToEvents({ events }: { events: InvestigationEvent[] }) {
  const map = useMap()
  useEffect(() => {
    const bounds = L.latLngBounds(events.map((e) => [e.latitude!, e.longitude!] as [number, number]))
    if (bounds.isValid()) map.fitBounds(bounds, { padding: [40, 40], maxZoom: 16 })
  }, [events, map])
  return null
}

/** Leaflet's marker-cluster plugin is not a React component, so we drive it from an effect. */
function ClusteredMarkers({
  events,
  timeZone,
  onSelect,
}: {
  events: InvestigationEvent[]
  timeZone: string
  onSelect: (event: InvestigationEvent) => void
}) {
  const map = useMap()
  const groupRef = useRef<L.MarkerClusterGroup | null>(null)
  // Markers are created once per data change; the ref lets their click handler always call the
  // latest onSelect without rebuilding every marker.
  const onSelectRef = useRef(onSelect)
  useEffect(() => {
    onSelectRef.current = onSelect
  }, [onSelect])

  useEffect(() => {
    const group = L.markerClusterGroup({ showCoverageOnHover: false, maxClusterRadius: 40 })
    groupRef.current = group
    map.addLayer(group)
    return () => {
      map.removeLayer(group)
    }
  }, [map])

  useEffect(() => {
    const group = groupRef.current
    if (!group) return
    group.clearLayers()
    for (const event of events) {
      const time = event.occurredAt ? timeInZone(event.occurredAt, timeZone, false) : '—'
      const marker = L.marker([event.latitude!, event.longitude!], {
        icon: L.divIcon({
          className: '',
          html: `<span class="falcon-pin" style="background:${categoryColor(event)}"></span>`,
          iconSize: [16, 16],
          iconAnchor: [8, 8],
        }),
        keyboard: true,
        title: `${time} ${eventTypeTerms[event.eventType].label}`,
        alt: `${time} ${eventTypeTerms[event.eventType].label}: ${event.description}`,
      })
      marker.bindTooltip(`<strong>${time}</strong> · ${escapeHtml(eventTypeTerms[event.eventType].label)}<br/>${escapeHtml(event.description)}`)
      marker.on('click', () => onSelectRef.current(event))
      group.addLayer(marker)
    }
  }, [events, timeZone])

  return null
}

/** Event text comes from evidence files: never insert it into HTML unescaped (XSS). */
function escapeHtml(text: string): string {
  return text.replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]!)
}
