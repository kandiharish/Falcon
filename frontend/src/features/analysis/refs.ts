/** What kind of thing an ID is, from its shape (backend: sink.ENTITY_PREFIX, reference counters). */
export type RefKind = 'evidence' | 'entity' | 'event' | 'correlation'

export function refKind(ref: string): RefKind | null {
  if (/^COR-\d{3,}$/.test(ref)) return 'correlation'
  if (/^[A-Z]{2,5}-\d{3,}$/.test(ref)) return 'evidence'
  if (/^E\d{3,}$/.test(ref)) return 'event'
  if (/^(P|PH|D|V|A|LOC|ORG|ART)\d{3,}$/.test(ref)) return 'entity'
  return null
}

export function refLink(caseRef: string, ref: string): string | null {
  switch (refKind(ref)) {
    case 'evidence':
      return `/investigations/${caseRef}/evidence/${ref}`
    case 'entity':
      return `/investigations/${caseRef}/entities/${ref}`
    case 'correlation':
      return `/investigations/${caseRef}/correlations/${ref}`
    default:
      return null // events have no page of their own yet; shown as plain IDs
  }
}

/** Split an answer into text and citation pieces: "[CCTV-001]" and a bare "CCTV-001" alike. */
export function splitCitations(text: string): ({ text: string } | { ref: string })[] {
  const parts: ({ text: string } | { ref: string })[] = []
  const pattern = /\[?\b((?:[A-Z]{2,5}-\d{3,})|(?:COR-\d{3,})|(?:(?:P|PH|D|V|A|E|LOC|ORG|ART)\d{3,}))\b\]?/g
  let last = 0
  for (const match of text.matchAll(pattern)) {
    if (match.index > last) parts.push({ text: text.slice(last, match.index) })
    parts.push({ ref: match[1] })
    last = match.index + match[0].length
  }
  if (last < text.length) parts.push({ text: text.slice(last) })
  return parts
}
