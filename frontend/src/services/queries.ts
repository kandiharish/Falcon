/**
 * TanStack Query hooks: the only way screens read server data.
 * Query keys are defined once here so caching and refetching stay consistent.
 */
import {
  keepPreviousData,
  MutationCache,
  QueryCache,
  QueryClient,
  useMutation,
  useQuery,
} from '@tanstack/react-query'
import { AdminService } from './adminService'
import { ApiError } from './apiClient'
import { AuthService, type LoginInput } from './authService'
import {
  InvestigationService,
  type InvestigationChanges,
  type InvestigationQuery,
  type NewInvestigation,
} from './investigationService'
import { SystemService } from './systemService'

export const queryKeys = {
  health: ['system', 'health'] as const,
  currentUser: ['auth', 'me'] as const,
  users: ['admin', 'users'] as const,
  investigations: ['investigations'] as const,
  investigationList: (query: InvestigationQuery) => ['investigations', 'list', query] as const,
  investigation: (ref: string) => ['investigations', 'detail', ref] as const,
  members: (ref: string) => ['investigations', 'detail', ref, 'members'] as const,
  activity: (ref: string) => ['investigations', 'detail', ref, 'activity'] as const,
  assignableUsers: ['investigations', 'assignable-users'] as const,
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

export const useInvestigations = (query: InvestigationQuery = {}, enabled = true) =>
  useQuery({
    queryKey: queryKeys.investigationList(query),
    queryFn: () => InvestigationService.list(query),
    enabled,
    placeholderData: keepPreviousData, // keep showing the old page while the next one loads
  })

export const useInvestigation = (reference: string | null) =>
  useQuery({
    queryKey: queryKeys.investigation(reference ?? 'none'),
    queryFn: () => InvestigationService.get(reference as string),
    enabled: reference !== null,
  })

export const useInvestigationMembers = (reference: string) =>
  useQuery({ queryKey: queryKeys.members(reference), queryFn: () => InvestigationService.members(reference) })

export const useInvestigationActivity = (reference: string) =>
  useQuery({
    queryKey: queryKeys.activity(reference),
    queryFn: () => InvestigationService.activity(reference),
    staleTime: 0,
  })

export const useAssignableUsers = (enabled: boolean) =>
  useQuery({ queryKey: queryKeys.assignableUsers, queryFn: InvestigationService.assignableUsers, enabled })

/** After any change, every cached investigation answer is marked stale and refetched. */
const refreshInvestigations = () =>
  queryClient.invalidateQueries({ queryKey: queryKeys.investigations })

export const useCreateInvestigation = () =>
  useMutation({
    mutationFn: (input: NewInvestigation) => InvestigationService.create(input),
    onSuccess: refreshInvestigations,
  })

export const useUpdateInvestigation = (reference: string) =>
  useMutation({
    mutationFn: (changes: InvestigationChanges) => InvestigationService.update(reference, changes),
    onSuccess: refreshInvestigations,
  })

export const useAddMember = (reference: string) =>
  useMutation({
    mutationFn: (email: string) => InvestigationService.addMember(reference, email),
    onSuccess: refreshInvestigations,
  })
