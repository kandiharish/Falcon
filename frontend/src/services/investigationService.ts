import type { InvestigationSummary } from '@/domain/types'
import { MOCK_INVESTIGATIONS } from './mock/fixtures'
import { simulateLatency } from './mock/latency'

/**
 * InvestigationService (plan §49).
 * Phase 2: returns fictional data. Phase 4: same functions call the real API —
 * the UI does not change.
 */
export const InvestigationService = {
  async list(): Promise<InvestigationSummary[]> {
    await simulateLatency()
    return MOCK_INVESTIGATIONS
  },

  async get(id: string): Promise<InvestigationSummary | null> {
    await simulateLatency()
    return MOCK_INVESTIGATIONS.find((investigation) => investigation.id === id) ?? null
  },
}
