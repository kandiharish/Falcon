import type { InvestigationEvent } from '@/domain/types'

/**
 * Where most of the action is. Events split into bursts wherever there is a long quiet gap
 * (a sixth of the whole span, at least an hour). If the biggest burst holds most events but
 * only a small part of the time — 18 events in one evening, one statement the next morning —
 * the timeline opens on that burst. Otherwise null: show everything.
 */
export function busiestPeriod(events: InvestigationEvent[]): [number, number] | null {
  const times = events.map((e) => new Date(e.occurredAt!).getTime()).sort((a, b) => a - b)
  if (times.length < 4) return null
  const span = times[times.length - 1] - times[0]
  const quiet = Math.max(3_600_000, span / 6)
  let best: [number, number, number] = [times[0], times[0], 1]
  let start = times[0]
  let count = 1
  for (let i = 1; i < times.length; i++) {
    if (times[i] - times[i - 1] > quiet) {
      start = times[i]
      count = 0
    }
    count += 1
    if (count > best[2]) best = [start, times[i], count]
  }
  const [from, to, inBurst] = best
  return inBurst >= times.length * 0.6 && inBurst < times.length && to - from < span * 0.5 ? [from, to] : null
}
