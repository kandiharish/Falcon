/** The report snapshot's shape (backend: report_service.build_content, schema falcon-report-v1). */
export interface ReportContent {
  schema: string
  report: { reference: string; title: string; generated_at: string; generated_by: string; include_pending: boolean }
  summary: {
    reference: string
    title: string
    case_type: string
    status: string
    priority: string
    stage: string
    location: string
    time_zone: string
    description: string
    lead: string
    team: string[]
    opened_at: string | null
  }
  scope: {
    period_from: string | null
    period_to: string | null
    counts: { evidence: number; entities: number; events: number; correlations: number }
    included: string
    excluded: string
  }
  evidence: {
    reference: string
    type: string
    description: string
    source: string
    collected_at: string | null
    location: string
    status: string
    sha256: string
    integrity_ok: boolean | null
    integrity_checked_at: string | null
    uploaded_by: string
    uploaded_at: string | null
  }[]
  sources: Record<string, number>
  entities: {
    reference: string
    type: string
    label: string
    review_status: string
    evidence_count: number
    event_count: number
    max_confidence: number | null
  }[]
  timeline: {
    reference: string
    occurred_at: string | null
    type: string
    description: string
    location: string
    evidence: string
    assertion: string
    confidence: number
    review_status: string
    participants: string[]
  }[]
  correlations: {
    reference: string
    evidence_a: string
    evidence_b: string
    level: string
    score: number
    reasons: string[]
    review_status: string
    review_note: string | null
    reviewed_by: string | null
  }[]
  relationships: { from: string; to: string; type: string; why: string; review_status: string }[]
  analyst_notes: {
    written: string
    observations: { reference: string; occurred_at: string | null; description: string; evidence: string }[]
  }
  limitations: { written: string; automatic: string[] }
  audit: { entries: number; by_action: Record<string, number>; last_activity: string | null; note: string }
}
