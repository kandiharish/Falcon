/**
 * TanStack Query hooks: the only way screens read server data.
 * Query keys are defined once here so caching and refetching stay consistent.
 */
import { MutationCache, QueryCache, QueryClient, useMutation, useQuery } from '@tanstack/react-query'
import { AdminService } from './adminService'
import { ApiError } from './apiClient'
import { AuthService, type LoginInput } from './authService'
import { InvestigationService } from './investigationService'
import { SystemService } from './systemService'

export const queryKeys = {
  health: ['system', 'health'] as const,
  currentUser: ['auth', 'me'] as const,
  users: ['admin', 'users'] as const,
  investigations: ['investigations'] as const,
  investigation: (id: string) => ['investigations', id] as const,
}

/** Any 401 means the session ended (expired, revoked, signed out elsewhere) → back to login. */
function onApiError(error: unknown) {
  if (error instanceof ApiError && error.status === 401) {
    queryClient.setQueryData(queryKeys.currentUser, null)
  }
}

export const queryClient = new QueryClient({
  queryCache: new QueryCache({ onError: onApiError }),
  mutationCache: new MutationCache({ onError: onApiError }),
  defaultOptions: {
    queries: {
      staleTime: 30_000, // data is "fresh" for 30 s: no refetch on every screen change
      retry: (failureCount, error) =>
        // Never retry "not signed in" / "not allowed"; retry other failures once.
        !(error instanceof ApiError && [401, 403].includes(error.status)) && failureCount < 1,
      refetchOnWindowFocus: false,
    },
  },
})

export const useSystemHealth = () =>
  useQuery({ queryKey: queryKeys.health, queryFn: SystemService.getHealth, staleTime: 0 })

export const useCurrentUser = () =>
  useQuery({ queryKey: queryKeys.currentUser, queryFn: AuthService.me, staleTime: 5 * 60_000 })

export const useLogin = () =>
  useMutation({
    mutationFn: (input: LoginInput) => AuthService.login(input),
    onSuccess: (user) => queryClient.setQueryData(queryKeys.currentUser, user),
  })

export const useLogout = () =>
  useMutation({
    mutationFn: AuthService.logout,
    onSettled: () => {
      // Forget every cached answer: the next user must not see this user's data.
      queryClient.clear()
      queryClient.setQueryData(queryKeys.currentUser, null)
    },
  })

export const useUsers = () => useQuery({ queryKey: queryKeys.users, queryFn: AdminService.listUsers })

export const useInvestigations = (enabled = true) =>
  useQuery({ queryKey: queryKeys.investigations, queryFn: InvestigationService.list, enabled })

export const useInvestigation = (id: string | null) =>
  useQuery({
    queryKey: queryKeys.investigation(id ?? 'none'),
    queryFn: () => InvestigationService.get(id as string),
    enabled: id !== null,
  })
