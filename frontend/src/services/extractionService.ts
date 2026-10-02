/**
 * ExtractionService: entities, events and what was extracted from each evidence item.
 */
import type {
  EntityDetailDto,
  EntityPageDto,
  EntitySummaryDto,
  EventDto,
  EventPageDto,
  ExtractedInformationDto,
  MentionDto,
} from '@/api/types'
import type {
  EntityDetail,
  EntityRef,
  EntitySummary,
  EntityType,
  EventType,
  ExtractedInformation,
  InvestigationEvent,
  Mention,
  ReviewStatus,
} from '@/domain/types'
import { apiGet, apiPost } from './apiClient'

export interface EntityQuery {
  entity_type?: EntityType
  search?: string
  review_status?: ReviewStatus
}

export interface EventQuery {
  event_type?: EventType
  entity?: string
  evidence?: string
  review_status?: ReviewStatus
}

export interface NewAnnotation {
  evidenceReference: string
  eventType: EventType
  occurredAt: string | null
  description: string
  participants: { entityReference: string; role: string }[]
  locationText: string
}

const ref = (dto: { reference: string; entity_type: EntityType; label: string }): EntityRef => ({
  reference: dto.reference,
  entityType: dto.entity_type,
  label: dto.label,
})

const toSummary = (dto: EntitySummaryDto): EntitySummary => ({
  ...ref(dto),
  reviewStatus: dto.review_status,
  mentionCount: dto.mention_count,
  evidenceCount: dto.evidence_count,
  eventCount: dto.event_count,
  maxConfidence: dto.max_confidence ?? null,
  assertionKinds: dto.assertion_kinds,
  attributes: dto.attributes as Record<string, unknown>,
  addedManually: dto.added_manually,
})

const toMention = (dto: MentionDto): Mention => ({
  evidenceReference: dto.evidence_reference,
  evidenceType: dto.evidence_type,
  evidenceDescription: dto.evidence_description,
  assertionKind: dto.assertion_kind,
  confidence: dto.confidence,
  extractor: dto.extractor,
  sourceLocation: dto.source_location,
  context: dto.context,
  createdAt: dto.created_at,
})

export const toEvent = (dto: EventDto): InvestigationEvent => ({
  reference: dto.reference,
  eventType: dto.event_type,
  occurredAt: dto.occurred_at ?? null,
  endedAt: dto.ended_at ?? null,
  latitude: dto.latitude ?? null,
  longitude: dto.longitude ?? null,
  locationText: dto.location_text,
  description: dto.description,
  evidenceReference: dto.evidence_reference,
  evidenceType: dto.evidence_type,
  assertionKind: dto.assertion_kind,
  confidence: dto.confidence,
  extractor: dto.extractor,
  sourceLocation: dto.source_location,
  reviewStatus: dto.review_status,
  attributes: dto.attributes as Record<string, unknown>,
  participants: dto.participants.map((p) => ({ ...ref(p), role: p.role })),
  addedManually: dto.added_manually,
})

const toDetail = (dto: EntityDetailDto): EntityDetail => ({
  ...toSummary(dto),
  mentions: dto.mentions.map(toMention),
  events: dto.events.map(toEvent),
})

const base = (caseRef: string) => `/investigations/${encodeURIComponent(caseRef)}`

function queryString(query: object): string {
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(query)) {
    if (value !== undefined && value !== '') params.set(key, String(value))
  }
  const text = params.toString()
  return text ? `?${text}` : ''
}

export const ExtractionService = {
  async listEntities(caseRef: string, query: EntityQuery = {}): Promise<{ items: EntitySummary[]; total: number }> {
    const page = await apiGet<EntityPageDto>(`${base(caseRef)}/entities${queryString({ ...query, limit: 200 })}`)
    return { items: page.items.map(toSummary), total: page.total }
  },

  async getEntity(caseRef: string, reference: string): Promise<EntityDetail> {
    return toDetail(await apiGet<EntityDetailDto>(`${base(caseRef)}/entities/${encodeURIComponent(reference)}`))
  },

  async reviewEntity(caseRef: string, reference: string, status: ReviewStatus, note?: string): Promise<EntityDetail> {
    return toDetail(
      await apiPost<EntityDetailDto>(`${base(caseRef)}/entities/${encodeURIComponent(reference)}/review`, {
        review_status: status,
        note,
      }),
    )
  },

  async addEntity(
    caseRef: string,
    input: { entityType: EntityType; value: string; evidenceReference: string; note: string },
  ): Promise<EntityDetail> {
    return toDetail(
      await apiPost<EntityDetailDto>(`${base(caseRef)}/entities`, {
        entity_type: input.entityType,
        value: input.value,
        evidence_reference: input.evidenceReference,
        note: input.note,
      }),
    )
  },

  async listEvents(caseRef: string, query: EventQuery = {}): Promise<{ items: InvestigationEvent[]; total: number }> {
    const page = await apiGet<EventPageDto>(`${base(caseRef)}/events${queryString({ ...query, limit: 500 })}`)
    return { items: page.items.map(toEvent), total: page.total }
  },

  async reviewEvent(caseRef: string, reference: string, status: ReviewStatus, note?: string): Promise<InvestigationEvent> {
    return toEvent(
      await apiPost<EventDto>(`${base(caseRef)}/events/${encodeURIComponent(reference)}/review`, {
        review_status: status,
        note,
      }),
    )
  },

  async addEvent(caseRef: string, input: NewAnnotation): Promise<InvestigationEvent> {
    return toEvent(
      await apiPost<EventDto>(`${base(caseRef)}/events`, {
        evidence_reference: input.evidenceReference,
        event_type: input.eventType,
        occurred_at: input.occurredAt,
        description: input.description,
        participants: input.participants.map((p) => ({ entity_reference: p.entityReference, role: p.role })),
        location_text: input.locationText,
      }),
    )
  },

  async extracted(caseRef: string, evidenceReference: string): Promise<ExtractedInformation> {
    const dto = await apiGet<ExtractedInformationDto>(
      `${base(caseRef)}/evidence/${encodeURIComponent(evidenceReference)}/extracted`,
    )
    return {
      evidenceReference: dto.evidence_reference,
      mentions: dto.mentions.map((m) => ({
        entity: ref(m.entity),
        assertionKind: m.assertion_kind,
        confidence: m.confidence,
        extractor: m.extractor,
        sourceLocation: m.source_location,
        context: m.context,
      })),
      events: dto.events.map(toEvent),
    }
  },
}
