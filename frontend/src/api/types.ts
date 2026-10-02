/**
 * Friendly names for the API shapes generated from the backend's OpenAPI document.
 * Regenerate after backend changes:  npm run api:types   (backend must be running)
 */
import type { components } from './schema'

type Schemas = components['schemas']

export type InvestigationDto = Schemas['InvestigationOut']
export type InvestigationPageDto = Schemas['InvestigationPage']
export type InvestigationCreateDto = Schemas['InvestigationCreate']
export type InvestigationUpdateDto = Schemas['InvestigationUpdate']
export type MemberDto = Schemas['MemberOut']
export type AssignableUserDto = Schemas['AssignableUser']
export type AuditEntryDto = Schemas['AuditEntry']
export type EvidenceDto = Schemas['EvidenceOut']
export type EvidencePageDto = Schemas['EvidencePage']
export type JobDto = Schemas['JobOut']
export type EntitySummaryDto = Schemas['EntitySummary']
export type EntityDetailDto = Schemas['EntityDetail']
export type EntityPageDto = Schemas['EntityPage']
export type MentionDto = Schemas['MentionOut']
export type EventDto = Schemas['EventOut']
export type EventPageDto = Schemas['EventPage']
export type ExtractedInformationDto = Schemas['ExtractedInformation']
export type EntityCreateDto = Schemas['EntityCreate']
export type EventCreateDto = Schemas['EventCreate']
