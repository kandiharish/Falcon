/**
 * Fictional demonstration data (plan §32). No real people, places or cases.
 * Lives ONLY here, behind the services — UI components never import this file.
 * Replaced by the real API in Phase 3 (user) and Phase 4 (investigations).
 */
import type { CurrentUser, InvestigationSummary } from '@/domain/types'

export const MOCK_INVESTIGATIONS: InvestigationSummary[] = [
  {
    id: 'CASE-2026-001',
    title: 'Riverside Warehouse Break-in',
    caseType: 'Burglary',
    status: 'active',
    priority: 'high',
    leadInvestigator: 'Insp. R. Varma',
    location: 'Riverside Industrial Zone',
    stage: 'correlation',
    updatedAt: '2026-09-29T17:42:00Z',
  },
  {
    id: 'CASE-2026-002',
    title: 'Harbor Street Card Fraud',
    caseType: 'Financial fraud',
    status: 'under_review',
    priority: 'medium',
    leadInvestigator: 'SI K. Iyer',
    location: 'Harbor Street Market',
    stage: 'review',
    updatedAt: '2026-09-28T09:15:00Z',
  },
  {
    id: 'CASE-2026-003',
    title: 'Northgate Vehicle Theft Series',
    caseType: 'Vehicle theft',
    status: 'active',
    priority: 'critical',
    leadInvestigator: 'Insp. R. Varma',
    location: 'Northgate District',
    stage: 'extraction',
    updatedAt: '2026-09-30T06:05:00Z',
  },
  {
    id: 'CASE-2026-004',
    title: 'Office Network Data Exfiltration',
    caseType: 'Cyber incident',
    status: 'draft',
    priority: 'medium',
    leadInvestigator: 'A. Menon',
    location: 'Eastline Business Park',
    stage: 'intake',
    updatedAt: '2026-09-30T11:20:00Z',
  },
  {
    id: 'CASE-2025-017',
    title: 'Central Metro Station Assault',
    caseType: 'Assault',
    status: 'closed',
    priority: 'high',
    leadInvestigator: 'SI K. Iyer',
    location: 'Central Metro Station',
    stage: 'closed',
    updatedAt: '2026-08-14T15:30:00Z',
  },
]

export const MOCK_CURRENT_USER: CurrentUser = {
  id: 'U-0007',
  displayName: 'A. Kumar',
  email: 'a.kumar@falcon.example',
  role: 'forensic_analyst',
}
