/**
 * TanStack Query hooks: the only way screens read server data.
 * Query keys are defined once here so caching and refetching stay consistent.
 */
import { QueryClient, useQuery } from '@tanstack/react-query'
import { InvestigationService } from './investigationService'
import { SystemService } from './systemService'
import { UserService } from './userService'

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000, // data is "fresh" for 30 s: no refetch on every screen change
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
})

export const queryKeys = {
  health: ['system', 'health'] as const,
  currentUser: ['user', 'me'] as const,
  investigations: ['investigations'] as const,
  investigation: (id: string) => ['investigations', id] as const,
}

export const useSystemHealth = () =>
  useQuery({ queryKey: queryKeys.health, queryFn: SystemService.getHealth, staleTime: 0 })

export const useCurrentUser = () =>
  useQuery({ queryKey: queryKeys.currentUser, queryFn: UserService.getCurrentUser })

export const useInvestigations = () =>
  useQuery({ queryKey: queryKeys.investigations, queryFn: InvestigationService.list })

export const useInvestigation = (id: string | null) =>
  useQuery({
    queryKey: queryKeys.investigation(id ?? 'none'),
    queryFn: () => InvestigationService.get(id as string),
    enabled: id !== null,
  })
