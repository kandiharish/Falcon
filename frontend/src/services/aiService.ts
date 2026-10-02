/**
 * AIService (plan §22–§23): local AI status, natural-language search, similar evidence,
 * and the Investigation Assistant (streamed step by step).
 */
import type { AISearchDto, AIStatusDto, ReindexDto, SimilarDto } from '@/api/types'
import type { AssistantEvent, AssistantTurn } from '@/domain/types'
import { apiGet, apiPost, apiStream } from './apiClient'

const base = (caseRef: string) => `/investigations/${encodeURIComponent(caseRef)}`

export const AIService = {
  status: () => apiGet<AIStatusDto>('/ai/status'),

  search: (caseRef: string, question: string) => apiPost<AISearchDto>(`${base(caseRef)}/ai/search`, { question }),

  similar: (caseRef: string, evidenceRef: string) =>
    apiGet<SimilarDto[]>(`${base(caseRef)}/evidence/${encodeURIComponent(evidenceRef)}/similar`),

  reindex: (caseRef: string) => apiPost<ReindexDto>(`${base(caseRef)}/ai/reindex`),

  ask: (caseRef: string, question: string, history: AssistantTurn[], signal?: AbortSignal) =>
    apiStream<AssistantEvent>(`${base(caseRef)}/assistant`, { question, history }, signal),
}
