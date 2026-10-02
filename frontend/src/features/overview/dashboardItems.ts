/** Dashboard counts turned into labelled bar items. */
import type { EvidenceStatus, EvidenceType } from '@/domain/types'
import { evidenceStatusTerms, evidenceTypeTerms } from '@/design-system/vocabulary'

export const sourceItems = (byType: Record<string, number>) =>
  Object.entries(byType).map(([type, value]) => ({ label: evidenceTypeTerms[type as EvidenceType]?.label ?? type, value }))

export const statusItems = (byStatus: Record<string, number>) =>
  Object.entries(byStatus).map(([status, value]) => ({ label: evidenceStatusTerms[status as EvidenceStatus]?.label ?? status, value }))
