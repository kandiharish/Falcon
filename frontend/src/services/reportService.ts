/**
 * ReportService (plan §24): generate, list and open investigation reports.
 * A report's content is a frozen JSON snapshot (see ReportContent) with a SHA-256 fingerprint.
 */
import type { ReportDetailDto, ReportSummaryDto } from '@/api/types'
import type { ReportContent } from '@/features/reports/content'
import { apiGet, apiPost } from './apiClient'

export interface ReportSummary {
  reference: string
  title: string
  status: 'generating' | 'ready' | 'failed'
  generatedBy: string
  createdAt: string
  completedAt: string | null
  sha256: string | null
  errorMessage: string | null
}

export interface ReportDetail extends ReportSummary {
  content: ReportContent | null
  intact: boolean
}

export interface NewReport {
  title: string
  analyst_notes: string
  limitations: string
  include_pending: boolean
}

const toSummary = (dto: ReportSummaryDto): ReportSummary => ({
  reference: dto.reference,
  title: dto.title,
  status: dto.status,
  generatedBy: dto.generated_by,
  createdAt: dto.created_at,
  completedAt: dto.completed_at ?? null,
  sha256: dto.content_sha256 ?? null,
  errorMessage: dto.error_message ?? null,
})

const toDetail = (dto: ReportDetailDto): ReportDetail => ({
  ...toSummary(dto),
  content: (dto.content as unknown as ReportContent | null) ?? null,
  intact: dto.intact,
})

const base = (caseRef: string) => `/investigations/${encodeURIComponent(caseRef)}/reports`

export const ReportService = {
  async list(caseRef: string): Promise<ReportSummary[]> {
    return (await apiGet<ReportSummaryDto[]>(base(caseRef))).map(toSummary)
  },
  async get(caseRef: string, reference: string): Promise<ReportDetail> {
    return toDetail(await apiGet<ReportDetailDto>(`${base(caseRef)}/${encodeURIComponent(reference)}`))
  },
  async generate(caseRef: string, input: NewReport): Promise<ReportDetail> {
    return toDetail(await apiPost<ReportDetailDto>(base(caseRef), input))
  },
  exportUrl: (caseRef: string, reference: string) => `/api${base(caseRef)}/${encodeURIComponent(reference)}/export`,
}
