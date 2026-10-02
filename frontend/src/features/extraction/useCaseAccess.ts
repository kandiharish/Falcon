import { useInvestigationContext } from '@/app/investigation-context'
import { can } from '@/services/authService'
import { useCurrentUser, useInvestigation } from '@/services/queries'

/** What the signed-in user may do with extracted information in a case. Server decides; this hides buttons. */
export function useCaseAccess(caseRef: string | null) {
  const { data: user } = useCurrentUser()
  const { data: investigation } = useInvestigation(caseRef)
  const onTeam = investigation?.myRoleInCase != null || user?.role === 'supervisor'
  const open = investigation ? !['closed', 'archived'].includes(investigation.status) : false
  return {
    canReview: can(user, 'evidence:verify') && onTeam,
    canContribute: can(user, 'evidence:upload') && onTeam && open,
    canCorrelate: can(user, 'correlation:review') && onTeam,
  }
}

/** The investigation's time zone (falls back to UTC while loading). */
export function useCaseTimeZone(caseRef: string | null): string {
  const { data: investigation } = useInvestigation(caseRef)
  return investigation?.timeZone ?? 'UTC'
}

export function useCurrentCase() {
  return useInvestigationContext((s) => s.currentInvestigationId)
}
