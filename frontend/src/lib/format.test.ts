import { describe, expect, it } from 'vitest'
import { formatBytes, timeAgo } from './format'

describe('formatting', () => {
  const now = Date.parse('2026-10-03T12:00:00Z')
  it('says how long ago, in words', () => {
    expect(timeAgo('2026-10-03T11:59:30Z', now)).toBe('just now')
    expect(timeAgo('2026-10-03T11:55:00Z', now)).toBe('5 min ago')
    expect(timeAgo('2026-10-03T09:00:00Z', now)).toBe('3 h ago')
    expect(timeAgo('2026-10-02T10:00:00Z', now)).toBe('yesterday')
    expect(timeAgo('2026-09-28T12:00:00Z', now)).toBe('5 days ago')
    expect(timeAgo('2026-10-03T12:05:00Z', now)).toBe('just now') // a clock slightly ahead
  })

  it('sizes files for people', () => {
    expect(formatBytes(512)).toMatch(/512\s?B/)
    expect(formatBytes(1536)).toMatch(/1\.5\s?KB/)
  })
})
