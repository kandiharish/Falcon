/**
 * Human labels, icons and tones for every domain value.
 * One place to change wording — never hard-code "Under Review" in a component.
 */
import {
  Archive,
  Building2,
  Camera,
  Car,
  CreditCard,
  DoorOpen,
  FileCode2,
  MapPin,
  MessageSquare,
  MessagesSquare,
  Phone,
  UserRound,
  FileArchive,
  FileText,
  Image as ImageIcon,
  Landmark,
  MapPinned,
  MessageSquareQuote,
  PhoneCall,
  Smartphone,
  Video,
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
  EntityType,
  EventType,
  EvidenceType,
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
  'evidence.uploaded': 'Uploaded the evidence',
  'evidence.downloaded': 'Downloaded the original file',
  'evidence.processed': 'Processing completed',
  'evidence.processing_failed': 'Processing failed',
  'evidence.integrity_checked': 'Checked integrity',
  'evidence.status_changed': 'Changed the review status',
  'evidence.reprocess_requested': 'Requested reprocessing',
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

export const evidenceTypeTerms: Record<EvidenceType, { label: string; icon: LucideIcon; hint: string }> = {
  video: { label: 'Video / CCTV', icon: Video, hint: 'MP4, MOV, AVI, MKV' },
  image: { label: 'Image', icon: ImageIcon, hint: 'JPEG, PNG, TIFF, HEIC' },
  document: { label: 'Document', icon: FileText, hint: 'PDF, DOCX, TXT' },
  gps: { label: 'GPS / location data', icon: MapPinned, hint: 'CSV, GPX, JSON' },
  mobile: { label: 'Mobile device data', icon: Smartphone, hint: 'CSV, JSON, XML, ZIP export' },
  call_records: { label: 'Call records', icon: PhoneCall, hint: 'CSV, JSON' },
  financial: { label: 'Financial transactions', icon: Landmark, hint: 'CSV, JSON, PDF' },
  vehicle: { label: 'Vehicle records', icon: Car, hint: 'CSV, JSON' },
  witness_statement: { label: 'Witness statement', icon: MessageSquareQuote, hint: 'PDF, DOCX, TXT' },
  digital_file: { label: 'Digital file', icon: FileArchive, hint: 'Any file except programs' },
  other: { label: 'Other', icon: FileArchive, hint: 'Any file except programs' },
}

/** A sensible first guess from the file name; the investigator can always change it. */
export function guessEvidenceType(filename: string): EvidenceType | null {
  const ext = filename.toLowerCase().split('.').pop() ?? ''
  if (['mp4', 'mov', 'avi', 'mkv', 'webm'].includes(ext)) return 'video'
  if (['jpg', 'jpeg', 'png', 'tif', 'tiff', 'heic', 'webp', 'bmp'].includes(ext)) return 'image'
  if (['pdf', 'docx', 'txt'].includes(ext)) return 'document'
  if (ext === 'gpx') return 'gps'
  return null
}

export const entityTypeTerms: Record<EntityType, { label: string; plural: string; icon: LucideIcon }> = {
  person: { label: 'Person', plural: 'People', icon: UserRound },
  phone_number: { label: 'Phone number', plural: 'Phone numbers', icon: Phone },
  device: { label: 'Device', plural: 'Devices', icon: Smartphone },
  vehicle: { label: 'Vehicle', plural: 'Vehicles', icon: Car },
  account: { label: 'Account', plural: 'Accounts', icon: CreditCard },
  location: { label: 'Location', plural: 'Locations', icon: MapPin },
  organization: { label: 'Organisation', plural: 'Organisations', icon: Building2 },
  digital_artifact: { label: 'Digital artefact', plural: 'Digital artefacts', icon: FileCode2 },
}

export const eventTypeTerms: Record<EventType, { label: string; icon: LucideIcon }> = {
  call_made: { label: 'Call made', icon: PhoneCall },
  message_sent: { label: 'Message sent', icon: MessageSquare },
  transaction_completed: { label: 'Transaction', icon: Landmark },
  location_recorded: { label: 'Location recorded', icon: MapPinned },
  vehicle_detected: { label: 'Vehicle detected', icon: Car },
  person_detected: { label: 'Person detected', icon: UserRound },
  device_detected: { label: 'Device detected', icon: Smartphone },
  person_entered_location: { label: 'Person entered location', icon: DoorOpen },
  photo_taken: { label: 'Photo taken', icon: Camera },
  video_recorded: { label: 'Video recorded', icon: Video },
  document_created: { label: 'Document dated', icon: FileText },
  communication: { label: 'Communication', icon: MessagesSquare },
  digital_artifact_created: { label: 'Digital artefact created', icon: FileCode2 },
  other: { label: 'Other event', icon: CircleDot },
}

/** Event types an analyst can record by hand while reviewing evidence. */
export const annotationEventTypes: EventType[] = [
  'person_detected',
  'vehicle_detected',
  'device_detected',
  'person_entered_location',
  'communication',
  'other',
]

export const participantRoleLabels: Record<string, string> = {
  caller: 'caller',
  callee: 'called',
  device: 'device',
  vehicle: 'vehicle',
  payer: 'paid',
  payee: 'received',
  subject: 'subject',
  involved: 'involved',
}
