/**
 * Human labels, icons and tones for every domain value.
 * One place to change wording — never hard-code "Under Review" in a component.
 */
import {
  Archive,
  BadgeCheck,
  Brain,
  CircleCheck,
  CircleDashed,
  CircleDot,
  CirclePause,
  Eye,
  FilePen,
  Fingerprint,
  Link2,
  Loader,
  PenLine,
  ScanSearch,
  TriangleAlert,
  Upload,
  CircleX,
  type LucideIcon,
} from 'lucide-react'
import type {
  AssertionKind,
  ConfidenceLevel,
  EvidenceStatus,
  InvestigationStatus,
  Priority,
  ReviewStatus,
  Role,
  TaskStatus,
  WorkflowStage,
} from '@/domain/types'
import type { Tone } from './tones'

export interface Term {
  label: string
  tone: Tone
  icon: LucideIcon
  description?: string
}

export const investigationStatusTerms: Record<InvestigationStatus, Term> = {
  draft: { label: 'Draft', tone: 'neutral', icon: FilePen },
  active: { label: 'Active', tone: 'info', icon: CircleDot },
  under_review: { label: 'Under Review', tone: 'warning', icon: Eye },
  suspended: { label: 'Suspended', tone: 'neutral', icon: CirclePause },
  closed: { label: 'Closed', tone: 'success', icon: CircleCheck },
  archived: { label: 'Archived', tone: 'neutral', icon: Archive },
}

export const evidenceStatusTerms: Record<EvidenceStatus, Term> = {
  uploaded: { label: 'Uploaded', tone: 'neutral', icon: Upload },
  processing: { label: 'Processing', tone: 'info', icon: Loader },
  processed: { label: 'Processed', tone: 'signal', icon: CircleCheck },
  verified: { label: 'Verified', tone: 'success', icon: BadgeCheck },
  requires_review: { label: 'Requires Review', tone: 'warning', icon: TriangleAlert },
  archived: { label: 'Archived', tone: 'neutral', icon: Archive },
}

export const reviewStatusTerms: Record<ReviewStatus, Term> = {
  pending: { label: 'Requires Review', tone: 'warning', icon: Eye },
  confirmed: { label: 'Analyst Confirmed', tone: 'success', icon: BadgeCheck },
  rejected: { label: 'Rejected', tone: 'danger', icon: CircleX },
}

export const taskStatusTerms: Record<TaskStatus, Term> = {
  todo: { label: 'To Do', tone: 'neutral', icon: CircleDashed },
  in_progress: { label: 'In Progress', tone: 'info', icon: Loader },
  review: { label: 'Review', tone: 'warning', icon: Eye },
  completed: { label: 'Completed', tone: 'success', icon: CircleCheck },
}

export const priorityTerms: Record<Priority, { label: string; tone: Tone; level: number }> = {
  low: { label: 'Low', tone: 'neutral', level: 1 },
  medium: { label: 'Medium', tone: 'info', level: 2 },
  high: { label: 'High', tone: 'warning', level: 3 },
  critical: { label: 'Critical', tone: 'danger', level: 4 },
}

/** Provenance labels (plan §13, §22): the investigator must always know where a fact came from. */
export const assertionTerms: Record<AssertionKind, Term> = {
  fact: {
    label: 'Fact',
    tone: 'success',
    icon: BadgeCheck,
    description: 'Directly recorded in original evidence and verified.',
  },
  extracted: {
    label: 'Extracted',
    tone: 'info',
    icon: ScanSearch,
    description: 'Read automatically from evidence (e.g. metadata, OCR text).',
  },
  detected: {
    label: 'Detected',
    tone: 'signal',
    icon: Fingerprint,
    description: 'Identified by an automated detector. May contain errors.',
  },
  correlated: {
    label: 'Correlated',
    tone: 'info',
    icon: Link2,
    description: 'Linked to other evidence by the correlation engine. Not proof.',
  },
  inferred: {
    label: 'Inferred',
    tone: 'inferred',
    icon: Brain,
    description: 'An AI-assisted interpretation. Must be reviewed by an analyst.',
  },
  user_entered: {
    label: 'User Entered',
    tone: 'neutral',
    icon: PenLine,
    description: 'Added manually by an investigator.',
  },
}

export const confidenceTerms: Record<ConfidenceLevel, { label: string; tone: Tone; bars: number }> = {
  high: { label: 'High', tone: 'success', bars: 3 },
  medium: { label: 'Medium', tone: 'warning', bars: 2 },
  low: { label: 'Low', tone: 'danger', bars: 1 },
}

/** Thresholds match the correlation engine (Phase 8): >=0.75 high, >=0.5 medium. */
export function confidenceLevel(score: number): ConfidenceLevel {
  if (score >= 0.75) return 'high'
  if (score >= 0.5) return 'medium'
  return 'low'
}

export const workflowStages: { stage: WorkflowStage; label: string }[] = [
  { stage: 'intake', label: 'Intake' },
  { stage: 'processing', label: 'Processing' },
  { stage: 'extraction', label: 'Extraction' },
  { stage: 'correlation', label: 'Correlation' },
  { stage: 'review', label: 'Review' },
  { stage: 'reporting', label: 'Reporting' },
  { stage: 'closed', label: 'Closed' },
]

export const roleLabels: Record<Role, string> = {
  investigation_officer: 'Investigation Officer',
  forensic_analyst: 'Forensic Analyst',
  evidence_analyst: 'Evidence Analyst',
  incident_investigator: 'Incident Investigator',
  supervisor: 'Supervisor',
  system_admin: 'System Administrator',
}

/**
 * Which status may follow which. Mirrors ALLOWED_TRANSITIONS in
 * backend/app/services/investigation_service.py — the server is the authority;
 * this copy only decides which buttons to offer.
 */
export const allowedTransitions: Record<InvestigationStatus, InvestigationStatus[]> = {
  draft: ['active', 'archived'],
  active: ['under_review', 'suspended', 'closed'],
  under_review: ['active', 'closed'],
  suspended: ['active', 'closed'],
  closed: ['active', 'archived'],
  archived: [],
}

/** Verb for moving *to* a status, e.g. "Activate", "Close investigation". */
export const transitionLabels: Record<InvestigationStatus, string> = {
  draft: 'Return to draft',
  active: 'Set active',
  under_review: 'Send for review',
  suspended: 'Suspend',
  closed: 'Close investigation',
  archived: 'Archive',
}

export const CASE_TYPES = [
  'Burglary',
  'Theft',
  'Vehicle theft',
  'Assault',
  'Financial fraud',
  'Cyber incident',
  'Missing person',
  'Narcotics',
  'Other',
] as const

export const auditActionLabels: Record<string, string> = {
  'investigation.created': 'Created the investigation',
  'investigation.updated': 'Updated the investigation',
  'investigation.member_added': 'Added a team member',
}

export const fieldLabels: Record<string, string> = {
  title: 'Title',
  description: 'Description',
  case_type: 'Case type',
  priority: 'Priority',
  status: 'Status',
  stage: 'Workflow stage',
  location: 'Location',
  tags: 'Tags',
  member: 'Member',
  role_in_case: 'Role in case',
}
