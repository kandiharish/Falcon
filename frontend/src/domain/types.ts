/**
 * FALCON domain vocabulary shared by the whole frontend.
 * These mirror plan.md §10, §11, §13, §22 and will be generated from the API schema later.
 */

export type InvestigationStatus =
  | 'draft'
  | 'active'
  | 'under_review'
  | 'suspended'
  | 'closed'
  | 'archived'

export type EvidenceStatus =
  | 'uploaded'
  | 'processing'
  | 'processed'
  | 'verified'
  | 'requires_review'
  | 'archived'

export type EvidenceType =
  | 'video'
  | 'image'
  | 'document'
  | 'gps'
  | 'mobile'
  | 'call_records'
  | 'financial'
  | 'vehicle'
  | 'witness_statement'
  | 'digital_file'
  | 'other'

export type ReviewStatus = 'pending' | 'confirmed' | 'rejected'

export type TaskStatus = 'todo' | 'in_progress' | 'review' | 'completed'

export type Priority = 'low' | 'medium' | 'high' | 'critical'

/** Where a piece of information came from — shown on every derived fact (plan §22). */
export type AssertionKind =
  | 'fact'
  | 'extracted'
  | 'detected'
  | 'correlated'
  | 'inferred'
  | 'user_entered'

export type ConfidenceLevel = 'high' | 'medium' | 'low'

/** Investigation workflow stages shown across the product (plan §44, condensed). */
export type WorkflowStage =
  | 'intake'
  | 'processing'
  | 'extraction'
  | 'correlation'
  | 'review'
  | 'reporting'
  | 'closed'

export interface Investigation {
  reference: string // e.g. CASE-2026-001
  title: string
  description: string
  caseType: string
  status: InvestigationStatus
  priority: Priority
  stage: WorkflowStage
  location: string
  timeZone: string // IANA, e.g. "Asia/Kolkata": times in this case are shown in this zone
  tags: string[]
  leadInvestigator: { id: string; displayName: string }
  teamSize: number
  myRoleInCase: 'lead' | 'member' | null
  counts: { evidence: number; entities: number; events: number; correlations: number }
  createdAt: string // ISO 8601
  updatedAt: string
}

export interface InvestigationMember {
  userId: string
  displayName: string
  email: string
  role: Role
  roleInCase: 'lead' | 'member'
  addedAt: string
}

export interface AuditEntry {
  id: number
  occurredAt: string
  actorEmail: string | null
  action: string
  previousState: Record<string, unknown> | null
  newState: Record<string, unknown> | null
  note: string | null
}

export type Role =
  | 'investigation_officer'
  | 'forensic_analyst'
  | 'evidence_analyst'
  | 'incident_investigator'
  | 'supervisor'
  | 'system_admin'

/** Permission strings checked by the API (backend/app/security/permissions.py). */
export type Permission =
  | 'investigation:read'
  | 'investigation:write'
  | 'evidence:read'
  | 'evidence:upload'
  | 'evidence:verify'
  | 'correlation:review'
  | 'report:generate'
  | 'task:manage'
  | 'audit:read'
  | 'users:read'
  | 'users:manage'
  | 'settings:manage'

export interface CurrentUser {
  id: string
  email: string
  displayName: string
  role: Role
  permissions: Permission[]
  mfaEnabled: boolean
  sessionExpiresAt: string // ISO 8601
}

export interface UserSummary {
  id: string
  email: string
  displayName: string
  role: Role
  isActive: boolean
  mfaEnabled: boolean
  locked: boolean
  lastLoginAt: string | null
  createdAt: string
}

export interface ProcessingStep {
  name: string
  label: string
  status: string // 'done' | 'failed'
  summary: string
  durationMs: number
}

export interface ProcessingJob {
  id: string
  status: 'queued' | 'running' | 'succeeded' | 'failed'
  progress: number
  currentStep: string | null
  steps: ProcessingStep[]
  attempts: number
  errorMessage: string | null
  createdAt: string
  startedAt: string | null
  finishedAt: string | null
}

export interface Evidence {
  reference: string // e.g. IMG-001
  investigationReference: string
  evidenceType: EvidenceType
  status: EvidenceStatus
  source: string
  description: string
  collectedAt: string | null
  locationText: string
  latitude: number | null
  longitude: number | null
  tags: string[]
  originalFilename: string
  mediaType: string
  sizeBytes: number
  sha256: string
  integrityCheckedAt: string | null
  integrityOk: boolean | null
  hasPreview: boolean
  fileMetadata: Record<string, unknown>
  uploadedBy: string
  createdAt: string
  latestJob: ProcessingJob | null
}

export type EntityType =
  | 'person'
  | 'phone_number'
  | 'device'
  | 'vehicle'
  | 'account'
  | 'location'
  | 'organization'
  | 'digital_artifact'

export type EventType =
  | 'call_made'
  | 'message_sent'
  | 'transaction_completed'
  | 'location_recorded'
  | 'vehicle_detected'
  | 'person_detected'
  | 'device_detected'
  | 'person_entered_location'
  | 'photo_taken'
  | 'video_recorded'
  | 'document_created'
  | 'communication'
  | 'digital_artifact_created'
  | 'other'

export interface EntityRef {
  reference: string // P001, PH001, V001 …
  entityType: EntityType
  label: string
}

export interface EntitySummary extends EntityRef {
  reviewStatus: ReviewStatus
  mentionCount: number
  evidenceCount: number
  eventCount: number
  maxConfidence: number | null
  assertionKinds: AssertionKind[]
  attributes: Record<string, unknown>
  addedManually: boolean
}

/** Where an entity appears in one evidence item, and how we know. */
export interface Mention {
  evidenceReference: string
  evidenceType: string
  evidenceDescription: string
  assertionKind: AssertionKind
  confidence: number
  extractor: string
  sourceLocation: string
  context: string
  createdAt: string
}

/** Named InvestigationEvent so it never clashes with the browser's built-in `Event`. */
export interface InvestigationEvent {
  reference: string // E001 …
  eventType: EventType
  occurredAt: string | null
  endedAt: string | null
  latitude: number | null
  longitude: number | null
  locationText: string
  description: string
  evidenceReference: string
  evidenceType: string
  assertionKind: AssertionKind
  confidence: number
  extractor: string
  sourceLocation: string
  reviewStatus: ReviewStatus
  attributes: Record<string, unknown>
  participants: (EntityRef & { role: string })[]
  addedManually: boolean
}

export interface EntityDetail extends EntitySummary {
  mentions: Mention[]
  events: InvestigationEvent[]
}

export interface ExtractedInformation {
  evidenceReference: string
  mentions: { entity: EntityRef; assertionKind: AssertionKind; confidence: number; extractor: string; sourceLocation: string; context: string }[]
  events: InvestigationEvent[]
}

export type CorrelationLevel = 'high' | 'medium' | 'low'
export type FactorKind = 'entity' | 'time' | 'location'

export interface CorrelationFactor {
  kind: FactorKind
  score: number // 0–1
  weight: number
  contribution: number // score × weight
  explanation: string
  details: Record<string, unknown>
}

/** A potential relationship between two evidence items — never a conclusion. */
export interface Correlation {
  reference: string // COR-004
  evidenceA: { reference: string; evidenceType: string; description: string }
  evidenceB: { reference: string; evidenceType: string; description: string }
  score: number
  level: CorrelationLevel
  factors: CorrelationFactor[]
  algorithm: string
  stale: boolean
  reviewStatus: ReviewStatus
  reviewNote: string | null
  reviewedBy: string | null
  reviewedAt: string | null
  createdAt: string
  updatedAt: string
}

export interface CorrelationDetail extends Correlation {
  supportingEvents: InvestigationEvent[]
}

export type GraphNodeKind = 'entity' | 'evidence' | 'event'
export type GraphEdgeType =
  | 'appears_in'
  | 'communicated_with'
  | 'connected_to'
  | 'related_evidence'
  | 'involved_in'
  | 'recorded_in'

export interface GraphNode {
  id: string // "entity:V001", "evidence:CCTV-001", "event:E002"
  kind: GraphNodeKind
  type: string // entity / evidence / event type
  reference: string
  label: string
  reviewStatus: ReviewStatus | null
  degree: number
  details: Record<string, unknown>
}

/** A link in the graph, always with the reason it exists. */
export interface GraphEdge {
  id: string
  source: string
  target: string
  type: GraphEdgeType
  why: string
  confidence: number
  reviewStatus: ReviewStatus
  assertionKinds: AssertionKind[]
  supportingEvidence: string[]
  supportingEvents: string[]
  details: Record<string, unknown>
}

export interface RelationshipGraph {
  nodes: GraphNode[]
  edges: GraphEdge[]
  totalNodes: number
  totalEdges: number
  truncated: boolean
}
