import { describe, expect, it } from 'vitest'
import { dayInZone, formatOffset, localInputToUtc, offsetMinutes, timeInZone, zoneLabel } from './time'

// The demo case: 20:30 in India is 15:00 UTC.
const BREAK_IN = '2026-09-28T15:00:00Z'

describe('time zones', () => {
  it('knows fixed and daylight-saving offsets', () => {
    expect(offsetMinutes('Asia/Kolkata', new Date(BREAK_IN))).toBe(330)
    expect(offsetMinutes('Europe/London', new Date('2026-07-01T12:00:00Z'))).toBe(60) // summer
    expect(offsetMinutes('Europe/London', new Date('2026-12-01T12:00:00Z'))).toBe(0) // winter
    expect(offsetMinutes('America/St_Johns', new Date('2026-12-01T12:00:00Z'))).toBe(-210)
  })

  it('labels zones the way investigators read them', () => {
    expect(formatOffset(330)).toBe('UTC+05:30')
    expect(formatOffset(-210)).toBe('UTC-03:30')
    expect(zoneLabel('UTC')).toBe('UTC')
    expect(zoneLabel('Asia/Kolkata', new Date(BREAK_IN))).toBe('Asia/Kolkata (UTC+05:30)')
  })

  it('shows a moment in the case zone, whatever the viewer’s zone', () => {
    expect(timeInZone(BREAK_IN, 'Asia/Kolkata')).toBe('20:30:00')
    expect(timeInZone(BREAK_IN, 'UTC', false)).toBe('15:00')
    // 23:30 UTC on the 28th is already the 29th in India: days belong to the case's zone.
    expect(dayInZone('2026-09-28T23:30:00Z', 'Asia/Kolkata')).toContain('29 September')
  })

  it('reads typed times in the case zone (round trip)', () => {
    expect(localInputToUtc('2026-09-28T20:30', 'Asia/Kolkata')).toBe('2026-09-28T15:00:00.000Z')
    // Across a daylight-saving change (London clocks go back on 25 Oct 2026).
    expect(localInputToUtc('2026-10-25T00:30', 'Europe/London')).toBe('2026-10-24T23:30:00.000Z')
    expect(localInputToUtc('2026-10-25T12:00', 'Europe/London')).toBe('2026-10-25T12:00:00.000Z')
  })
})
