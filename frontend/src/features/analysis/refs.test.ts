import { describe, expect, it } from 'vitest'
import { refKind, refLink, splitCitations } from './refs'

describe('reference IDs', () => {
  it('recognises what an ID is from its shape', () => {
    expect(refKind('CCTV-001')).toBe('evidence')
    expect(refKind('COR-004')).toBe('correlation')
    expect(refKind('E012')).toBe('event')
    expect(refKind('PH001')).toBe('entity')
    expect(refKind('ORG002')).toBe('entity')
    expect(refKind('hello')).toBeNull()
  })

  it('links to the right page, and leaves events plain', () => {
    expect(refLink('CASE-2026-001', 'V001')).toBe('/investigations/CASE-2026-001/entities/V001')
    expect(refLink('CASE-2026-001', 'COR-004')).toBe('/investigations/CASE-2026-001/correlations/COR-004')
    expect(refLink('CASE-2026-001', 'E002')).toBeNull()
  })
})

describe('citations in assistant answers', () => {
  it('finds bracketed and bare IDs, but not phone numbers or plates', () => {
    const parts = splitCitations('PH001 called +1 202-555-0102 at 20:33 [E011]; van ZZ99 ZZ 0001 seen in CALL-001.')
    const refs = parts.flatMap((p) => ('ref' in p ? [p.ref] : []))
    expect(refs).toEqual(['PH001', 'E011', 'CALL-001'])
    // The text around the citations is kept exactly.
    expect(parts.map((p) => ('ref' in p ? `<${p.ref}>` : p.text)).join('')).toBe(
      '<PH001> called +1 202-555-0102 at 20:33 <E011>; van ZZ99 ZZ 0001 seen in <CALL-001>.',
    )
  })
})
