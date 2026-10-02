/**
 * Time-zone helpers built on the browser's Intl API (no date library needed).
 *
 * FALCON stores every time in UTC. An investigation has a time zone (e.g. Asia/Kolkata);
 * times are SHOWN in that zone, and times an investigator TYPES are read in that zone,
 * so "20:30" means the same moment for everyone, wherever they sit.
 */

export const browserTimeZone = (): string => Intl.DateTimeFormat().resolvedOptions().timeZone

/** Every IANA zone the browser knows (for pickers). */
export const allTimeZones = (): string[] =>
  typeof Intl.supportedValuesOf === 'function' ? Intl.supportedValuesOf('timeZone') : ['UTC']

/** Minutes the zone is ahead of UTC at a given moment (handles daylight saving). */
export function offsetMinutes(timeZone: string, at: Date = new Date()): number {
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone,
    hourCycle: 'h23',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  }).formatToParts(at)
  const get = (type: string) => Number(parts.find((p) => p.type === type)?.value)
  const asUtc = Date.UTC(get('year'), get('month') - 1, get('day'), get('hour'), get('minute'), get('second'))
  return Math.round((asUtc - Math.floor(at.getTime() / 1000) * 1000) / 60000)
}

/** "UTC+05:30" */
export function formatOffset(minutes: number): string {
  const sign = minutes < 0 ? '-' : '+'
  const abs = Math.abs(minutes)
  return `UTC${sign}${String(Math.floor(abs / 60)).padStart(2, '0')}:${String(abs % 60).padStart(2, '0')}`
}

/** "Asia/Kolkata (UTC+05:30)" */
export function zoneLabel(timeZone: string, at: Date = new Date()): string {
  return timeZone === 'UTC' ? 'UTC' : `${timeZone} (${formatOffset(offsetMinutes(timeZone, at))})`
}

export function formatInZone(iso: string, timeZone: string, options: Intl.DateTimeFormatOptions = { dateStyle: 'medium', timeStyle: 'short' }): string {
  return new Intl.DateTimeFormat('en-GB', { timeZone, ...options }).format(new Date(iso))
}

export const timeInZone = (iso: string, timeZone: string, withSeconds = true) =>
  formatInZone(iso, timeZone, { hour: '2-digit', minute: '2-digit', ...(withSeconds ? { second: '2-digit' } : {}), hourCycle: 'h23' })

export const dayInZone = (iso: string, timeZone: string) =>
  formatInZone(iso, timeZone, { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })

/**
 * "2026-09-28T20:30" typed into <input type="datetime-local">, meant in `timeZone`,
 * → the real moment in ISO UTC.
 */
export function localInputToUtc(value: string, timeZone: string): string {
  const [date, time = '00:00'] = value.split('T')
  const [y, m, d] = date.split('-').map(Number)
  const [hh, mm, ss = 0] = time.split(':').map(Number)
  const naiveUtc = Date.UTC(y, m - 1, d, hh, mm, ss)
  // The offset at that local time (two passes settle daylight-saving edges).
  let offset = offsetMinutes(timeZone, new Date(naiveUtc))
  offset = offsetMinutes(timeZone, new Date(naiveUtc - offset * 60000))
  return new Date(naiveUtc - offset * 60000).toISOString()
}
