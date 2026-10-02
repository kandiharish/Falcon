/**
 * CorrelationService (plan §49): run the engine, list potential relationships, review them.
 */
import type { CorrelationDetailDto, CorrelationDto, CorrelationPageDto, CorrelationRunDto } from '@/api/types'
import type { Correlation, CorrelationDetail, CorrelationLevel, ReviewStatus } from '@/domain/types'
import { apiGet, apiPost } from './apiClient'
import { toEvent } from './extractionService'

export interface CorrelationQuery {
  level?: CorrelationLevel
  review_status?: ReviewStatus
  evidence?: string
  include_stale?: boolean
}

const toCorrelation = (dto: CorrelationDto): Correlation => ({
  reference: dto.reference,
  evidenceA: { reference: dto.evidence_a.reference, evidenceType: dto.evidence_a.evidence_type, description: dto.evidence_a.description },
  evidenceB: { reference: dto.evidence_b.reference, evidenceType: dto.evidence_b.evidence_type, description: dto.evidence_b.description },
  score: dto.score,
  level: dto.level,
  factors: dto.factors.map((f) => ({ ...f, details: f.details as Record<string, unknown> })),
  algorithm: dto.algorithm,
  stale: dto.stale,
  reviewStatus: dto.review_status,
  reviewNote: dto.review_note ?? null,
  reviewedBy: dto.reviewed_by ?? null,
  reviewedAt: dto.reviewed_at ?? null,
  createdAt: dto.created_at,
  updatedAt: dto.updated_at,
})

const toDetail = (dto: CorrelationDetailDto): CorrelationDetail => ({
  ...toCorrelation(dto),
  supportingEvents: dto.supporting_events.map(toEvent),
})

const base = (caseRef: string) => `/investigations/${encodeURIComponent(caseRef)}/correlations`

function queryString(query: CorrelationQuery): string {
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(query)) {
    if (value !== undefined && value !== '') params.set(key, String(value))
  }
  const text = params.toString()
  return text ? `?${text}` : ''
}

export const CorrelationService = {
  async list(caseRef: string, query: CorrelationQuery = {}): Promise<{ items: Correlation[]; total: number }> {
    const page = await apiGet<CorrelationPageDto>(`${base(caseRef)}${queryString(query)}`)
    return { items: page.items.map(toCorrelation), total: page.total }
  },

  async get(caseRef: string, reference: string): Promise<CorrelationDetail> {
    return toDetail(await apiGet<CorrelationDetailDto>(`${base(caseRef)}/${encodeURIComponent(reference)}`))
  },

  async run(caseRef: string): Promise<CorrelationRunDto> {
    return apiPost<CorrelationRunDto>(`${base(caseRef)}/run`)
  },

  async review(caseRef: string, reference: string, status: ReviewStatus, note?: string): Promise<CorrelationDetail> {
    return toDetail(
      await apiPost<CorrelationDetailDto>(`${base(caseRef)}/${encodeURIComponent(reference)}/review`, {
        review_status: status,
        note,
      }),
    )
  },
}
