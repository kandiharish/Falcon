/**
 * "Which investigation am I working on?" — the one piece of UI state every screen shares.
 * Zustand = a tiny global store; persist = remembered across page reloads.
 */
import { create } from 'zustand'
import { persist } from 'zustand/middleware'

interface InvestigationContextState {
  /** Case reference, e.g. CASE-2026-001. */
  currentInvestigationId: string | null
  setCurrentInvestigation: (reference: string | null) => void
}

export const useInvestigationContext = create<InvestigationContextState>()(
  persist(
    (set) => ({
      currentInvestigationId: null,
      setCurrentInvestigation: (reference) => set({ currentInvestigationId: reference }),
    }),
    { name: 'falcon-current-investigation' },
  ),
)
