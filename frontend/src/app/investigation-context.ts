/**
 * "Which investigation am I working on?" — the one piece of UI state every screen shares.
 * Zustand = a tiny global store; persist = remembered across page reloads.
 */
import { create } from 'zustand'
import { persist } from 'zustand/middleware'

interface InvestigationContextState {
  currentInvestigationId: string | null
  setCurrentInvestigation: (id: string) => void
}

export const useInvestigationContext = create<InvestigationContextState>()(
  persist(
    (set) => ({
      currentInvestigationId: 'CASE-2026-001',
      setCurrentInvestigation: (id) => set({ currentInvestigationId: id }),
    }),
    { name: 'falcon-current-investigation' },
  ),
)
