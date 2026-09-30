/**
 * Route guards. The backend is the real security boundary (it returns 401/403);
 * these guards only decide what to *show*, so users are never sent to screens they can't use.
 */
import type { ReactNode } from 'react'
import { Navigate, Outlet, useLocation } from 'react-router'
import { ShieldAlert } from 'lucide-react'
import type { Permission } from '@/domain/types'
import { can } from '@/services/authService'
import { useCurrentUser } from '@/services/queries'
import { AppLoading } from '@/app-shell/AppLoading'
import { EmptyState, ErrorState } from '@/design-system/states'

/** Signed in? Show the app. Not signed in? Go to /login and come back afterwards. */
export function RequireAuth() {
  const { data: user, isPending, isError, refetch, isRefetching } = useCurrentUser()
  const location = useLocation()

  if (isPending) return <AppLoading />
  if (isError) {
    return (
      <div className="mx-auto max-w-lg p-10">
        <ErrorState
          title="FALCON could not check your session"
          description="The server could not be reached. Check that the backend is running, then try again."
          onRetry={() => refetch()}
          retrying={isRefetching}
        />
      </div>
    )
  }
  if (!user) {
    const next = location.pathname + location.search
    return <Navigate to={`/login${next !== '/' ? `?next=${encodeURIComponent(next)}` : ''}`} replace />
  }
  return <Outlet />
}

/** Inside the app: hide a screen the user's role cannot use, and explain why. */
export function RequirePermission({
  permission,
  children,
}: {
  permission: Permission
  children: ReactNode
}) {
  const { data: user } = useCurrentUser()
  if (!can(user, permission)) {
    return (
      <div className="mx-auto max-w-3xl pt-10">
        <EmptyState
          icon={ShieldAlert}
          title="Access restricted"
          description="Your role does not include access to this area. Contact your supervisor if you need it."
        />
      </div>
    )
  }
  return children
}
