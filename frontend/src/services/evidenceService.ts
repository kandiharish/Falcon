/**
 * EvidenceService (plan §49): every evidence action the screens need.
 */
import type { AuditEntryDto, EvidenceDto, EvidencePageDto, JobDto } from '@/api/types'
import type { AuditEntry, Evidence, EvidenceStatus, EvidenceType, ProcessingJob } from '@/domain/types'
import { apiGet, apiPost, apiUpload } from './apiClient'

export interface EvidenceQuery {
  search?: string
  evidence_type?: EvidenceType
  status?: EvidenceStatus
  limit?: number
  offset?: number
}

export interface EvidencePage {
  items: Evidence[]
  total: number
  limit: number
  offset: number
}

export interface NewEvidence {
  file: File
  evidenceType: EvidenceType
  source: string
  description: string
  collectedAt: string | null // ISO 8601
  locationText: string
  latitude: number | null
  longitude: number | null
  tags: string[]
}

const toJob = (dto: JobDto): ProcessingJob => ({
  id: dto.id,
  status: dto.status,
  progress: dto.progress,
  currentStep: dto.current_step ?? null,
  steps: dto.steps.map((s) => ({
    name: s.name,
    label: s.label,
    status: s.status,
    summary: s.summary,
    durationMs: s.duration_ms,
  })),
  attempts: dto.attempts,
  errorMessage: dto.error_message ?? null,
  createdAt: dto.created_at,
  startedAt: dto.started_at ?? null,
  finishedAt: dto.finished_at ?? null,
})

export const toEvidence = (dto: EvidenceDto): Evidence => ({
  reference: dto.reference,
  investigationReference: dto.investigation_reference,
  evidenceType: dto.evidence_type,
  status: dto.status,
  source: dto.source,
  description: dto.description,
  collectedAt: dto.collected_at ?? null,
  locationText: dto.location_text,
  latitude: dto.latitude ?? null,
  longitude: dto.longitude ?? null,
  tags: dto.tags,
  originalFilename: dto.original_filename,
  mediaType: dto.media_type,
  sizeBytes: dto.size_bytes,
  sha256: dto.sha256,
  integrityCheckedAt: dto.integrity_checked_at ?? null,
  integrityOk: dto.integrity_ok ?? null,
  hasPreview: dto.has_preview,
  fileMetadata: dto.file_metadata as Record<string, unknown>,
  uploadedBy: dto.uploaded_by,
  createdAt: dto.created_at,
  latestJob: dto.latest_job ? toJob(dto.latest_job) : null,
})

const base = (caseRef: string) => `/investigations/${encodeURIComponent(caseRef)}/evidence`
const item = (caseRef: string, ref: string) => `${base(caseRef)}/${encodeURIComponent(ref)}`

function queryString(query: EvidenceQuery): string {
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(query)) {
    if (value !== undefined && value !== '') params.set(key, String(value))
  }
  const text = params.toString()
  return text ? `?${text}` : ''
}

export const EvidenceService = {
  async list(caseRef: string, query: EvidenceQuery = {}): Promise<EvidencePage> {
    const page = await apiGet<EvidencePageDto>(`${base(caseRef)}${queryString(query)}`)
    return { ...page, items: page.items.map(toEvidence) }
  },

  async get(caseRef: string, ref: string): Promise<Evidence> {
    return toEvidence(await apiGet<EvidenceDto>(item(caseRef, ref)))
  },

  async upload(caseRef: string, input: NewEvidence, onProgress?: (percent: number) => void): Promise<Evidence> {
    const form = new FormData()
    form.set('file', input.file)
    form.set('evidence_type', input.evidenceType)
    form.set('source', input.source)
    form.set('description', input.description)
    form.set('location_text', input.locationText)
    form.set('tags', input.tags.join(','))
    if (input.collectedAt) form.set('collected_at', input.collectedAt)
    if (input.latitude !== null && input.longitude !== null) {
      form.set('latitude', String(input.latitude))
      form.set('longitude', String(input.longitude))
    }
    return toEvidence(await apiUpload<EvidenceDto>(base(caseRef), form, onProgress))
  },

  async verifyIntegrity(caseRef: string, ref: string): Promise<Evidence> {
    return toEvidence(await apiPost<EvidenceDto>(`${item(caseRef, ref)}/verify-integrity`))
  },

  async changeStatus(caseRef: string, ref: string, status: EvidenceStatus, note?: string): Promise<Evidence> {
    return toEvidence(await apiPost<EvidenceDto>(`${item(caseRef, ref)}/status`, { status, note }))
  },

  async reprocess(caseRef: string, ref: string): Promise<Evidence> {
    return toEvidence(await apiPost<EvidenceDto>(`${item(caseRef, ref)}/reprocess`))
  },

  async history(caseRef: string, ref: string): Promise<AuditEntry[]> {
    const rows = await apiGet<AuditEntryDto[]>(`${item(caseRef, ref)}/history`)
    return rows.map((r) => ({
      id: r.id,
      occurredAt: r.occurred_at,
      actorEmail: r.actor_email ?? null,
      action: r.action,
      previousState: (r.previous_state as Record<string, unknown> | null) ?? null,
      newState: (r.new_state as Record<string, unknown> | null) ?? null,
      note: r.note ?? null,
    }))
  },

  contentUrl: (caseRef: string, ref: string) => `/api${item(caseRef, ref)}/content`,
  previewUrl: (caseRef: string, ref: string) => `/api${item(caseRef, ref)}/preview`,
}

/** True while the evidence is waiting for or going through processing. */
export const isProcessing = (evidence: Evidence) =>
  evidence.latestJob?.status === 'queued' || evidence.latestJob?.status === 'running'
