/**
 * Insights (what to check next) and court-ready documents: Section 63 certificates,
 * requisition letters and the court bundle. Documents are DRAFTS the officer completes.
 */
import type { DraftDocumentDto, InsightsDto } from '@/api/types'
import { apiGet } from './apiClient'

export type Insight = InsightsDto['items'][number]
export type DraftDocument = DraftDocumentDto
export type LetterKind = 'telecom_subscriber' | 'telecom_imei' | 'bank_kyc' | 'cctv_preservation'

export interface LetterRequest {
  kind: LetterKind
  entity: string
  from?: string
  to?: string
  places?: string[]
}

const base = (caseRef: string) => `/investigations/${encodeURIComponent(caseRef)}`

/** The letter request an insight suggests, as URL search params (for a shareable page URL). */
export function letterParams(letter: LetterRequest): string {
  const params = new URLSearchParams({ entity: letter.entity })
  if (letter.from && letter.to) {
    params.set('from', letter.from)
    params.set('to', letter.to)
  }
  for (const place of letter.places ?? []) params.append('place', place)
  return params.toString()
}

export const DocumentsService = {
  insights: (caseRef: string) => apiGet<InsightsDto>(`${base(caseRef)}/insights`),
  certificate: (caseRef: string, evidenceRef: string) =>
    apiGet<DraftDocumentDto>(`${base(caseRef)}/evidence/${encodeURIComponent(evidenceRef)}/certificate`),
  letter: (caseRef: string, kind: LetterKind, query: string) =>
    apiGet<DraftDocumentDto>(`${base(caseRef)}/letters/${kind}?${query}`),
  bundleUrl: (caseRef: string) => `/api${base(caseRef)}/bundle`,
}
