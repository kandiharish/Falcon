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

export interface InvestigationSummary {
  id: string
  title: string
  caseType: string
  status: InvestigationStatus
  priority: Priority
  leadInvestigator: string
  location: string
  stage: WorkflowStage
  updatedAt: string // ISO 8601
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
