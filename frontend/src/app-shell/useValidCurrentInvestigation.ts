import { useEffect } from 'react'
import { useInvestigationContext } from '@/app/investigation-context'
import { can } from '@/services/authService'
import { useCurrentUser, useInvestigation, useInvestigations } from '@/services/queries'

/**
 * Keeps "current investigation" pointing at a case this user can actually see.
 * The choice is remembered in the browser, so after a different person signs in it may
 * point at a case outside their team — then we fall back to their most recent case.
 */
export function useValidCurrentInvestigation() {
  const { data: user } = useCurrentUser()
  const allowed = can(user, 'investigation:read')
  const { currentInvestigationId, setCurrentInvestigation } = useInvestigationContext()
  const current = useInvestigation(allowed ? currentInvestigationId : null)
  const { data: page } = useInvestigations({ limit: 1 }, allowed)

  useEffect(() => {
    if (!allowed || !page) return
    const missing = currentInvestigationId === null || current.isError
    if (missing) setCurrentInvestigation(page.items[0]?.reference ?? null)
  }, [allowed, page, currentInvestigationId, current.isError, setCurrentInvestigation])
}
