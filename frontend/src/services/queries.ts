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
import { CorrelationService, type CorrelationQuery } from './correlationService'
import { GraphService, type GraphQuery } from './graphService'
import { AIService } from './aiService'
import { ApiError } from './apiClient'
import { AuthService, type LoginInput } from './authService'
import { EvidenceService, isProcessing, type EvidenceQuery, type NewEvidence } from './evidenceService'
import { ExtractionService, type EntityQuery, type EventQuery, type NewAnnotation } from './extractionService'
import type { EntityType, ReviewStatus } from '@/domain/types'
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
  evidence: (caseRef: string) => ['evidence', caseRef] as const,
  evidenceList: (caseRef: string, query: EvidenceQuery) => ['evidence', caseRef, 'list', query] as const,
  evidenceItem: (caseRef: string, ref: string) => ['evidence', caseRef, 'item', ref] as const,
  evidenceHistory: (caseRef: string, ref: string) => ['evidence', caseRef, 'item', ref, 'history'] as const,
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

// ---------- Evidence ----------------------------------------------------------------------

const POLL_MS = 2000 // while something is processing, ask for progress every 2 seconds

export const useEvidenceList = (caseRef: string | null, query: EvidenceQuery = {}) =>
  useQuery({
    queryKey: queryKeys.evidenceList(caseRef ?? 'none', query),
    queryFn: () => EvidenceService.list(caseRef as string, query),
    enabled: caseRef !== null,
    placeholderData: keepPreviousData,
    refetchInterval: (q) => (q.state.data?.items.some(isProcessing) ? POLL_MS : false),
  })

export const useEvidence = (caseRef: string, ref: string) =>
  useQuery({
    queryKey: queryKeys.evidenceItem(caseRef, ref),
    queryFn: () => EvidenceService.get(caseRef, ref),
    refetchInterval: (q) => (q.state.data && isProcessing(q.state.data) ? POLL_MS : false),
  })

export const useEvidenceHistory = (caseRef: string, ref: string) =>
  useQuery({
    queryKey: queryKeys.evidenceHistory(caseRef, ref),
    queryFn: () => EvidenceService.history(caseRef, ref),
    staleTime: 0,
  })

/** Evidence changes affect evidence lists AND investigation counts. */
const refreshEvidence = (caseRef: string) =>
  Promise.all([
    queryClient.invalidateQueries({ queryKey: queryKeys.evidence(caseRef) }),
    queryClient.invalidateQueries({ queryKey: queryKeys.investigations }),
  ])

export const useUploadEvidence = (caseRef: string) =>
  useMutation({
    mutationFn: ({ input, onProgress }: { input: NewEvidence; onProgress?: (p: number) => void }) =>
      EvidenceService.upload(caseRef, input, onProgress),
    onSuccess: () => refreshEvidence(caseRef),
  })

export const useEvidenceAction = (caseRef: string, ref: string) =>
  useMutation({
    mutationFn: (action: { kind: 'verify-integrity' } | { kind: 'reprocess' } | { kind: 'status'; status: 'verified' | 'requires_review' | 'processed'; note?: string }) => {
      if (action.kind === 'verify-integrity') return EvidenceService.verifyIntegrity(caseRef, ref)
      if (action.kind === 'reprocess') return EvidenceService.reprocess(caseRef, ref)
      return EvidenceService.changeStatus(caseRef, ref, action.status, action.note)
    },
    onSuccess: () => refreshEvidence(caseRef),
  })

// ---------- Entities & events -------------------------------------------------------------

export const extractionKeys = {
  all: (caseRef: string) => ['extraction', caseRef] as const,
  entities: (caseRef: string, query: EntityQuery) => ['extraction', caseRef, 'entities', query] as const,
  entity: (caseRef: string, ref: string) => ['extraction', caseRef, 'entity', ref] as const,
  events: (caseRef: string, query: EventQuery) => ['extraction', caseRef, 'events', query] as const,
  extracted: (caseRef: string, evidenceRef: string) => ['extraction', caseRef, 'extracted', evidenceRef] as const,
}

export const useEntities = (caseRef: string | null, query: EntityQuery = {}) =>
  useQuery({
    queryKey: extractionKeys.entities(caseRef ?? 'none', query),
    queryFn: () => ExtractionService.listEntities(caseRef as string, query),
    enabled: caseRef !== null,
    placeholderData: keepPreviousData,
  })

export const useEntity = (caseRef: string, ref: string) =>
  useQuery({ queryKey: extractionKeys.entity(caseRef, ref), queryFn: () => ExtractionService.getEntity(caseRef, ref) })

export const useEvents = (caseRef: string | null, query: EventQuery = {}) =>
  useQuery({
    queryKey: extractionKeys.events(caseRef ?? 'none', query),
    queryFn: () => ExtractionService.listEvents(caseRef as string, query),
    enabled: caseRef !== null,
    placeholderData: keepPreviousData,
  })

export const useExtracted = (caseRef: string, evidenceRef: string, enabled = true) =>
  useQuery({
    queryKey: extractionKeys.extracted(caseRef, evidenceRef),
    queryFn: () => ExtractionService.extracted(caseRef, evidenceRef),
    enabled,
  })

/** Any change to extracted information refreshes entity/event lists and case counts. */
const refreshExtraction = (caseRef: string) =>
  Promise.all([
    queryClient.invalidateQueries({ queryKey: extractionKeys.all(caseRef) }),
    queryClient.invalidateQueries({ queryKey: ['graph', caseRef] }),
    queryClient.invalidateQueries({ queryKey: queryKeys.investigations }),
  ])

export const useReview = (caseRef: string) =>
  useMutation({
    // The screens re-read the data afterwards, so the response itself is not needed.
    mutationFn: async (input: {
      kind: 'entity' | 'event'
      reference: string
      status: ReviewStatus
      note?: string
    }): Promise<void> => {
      if (input.kind === 'entity') {
        await ExtractionService.reviewEntity(caseRef, input.reference, input.status, input.note)
      } else {
        await ExtractionService.reviewEvent(caseRef, input.reference, input.status, input.note)
      }
    },
    onSuccess: () => refreshExtraction(caseRef),
  })

export const useAddAnnotation = (caseRef: string) =>
  useMutation({
    mutationFn: (input: NewAnnotation) => ExtractionService.addEvent(caseRef, input),
    onSuccess: () => refreshExtraction(caseRef),
  })

export const useAddEntity = (caseRef: string) =>
  useMutation({
    mutationFn: (input: { entityType: EntityType; value: string; evidenceReference: string; note: string }) =>
      ExtractionService.addEntity(caseRef, input),
    onSuccess: () => refreshExtraction(caseRef),
  })

// ---------- Correlations -----------------------------------------------------------------

export const correlationKeys = {
  all: (caseRef: string) => ['correlations', caseRef] as const,
  list: (caseRef: string, query: CorrelationQuery) => ['correlations', caseRef, 'list', query] as const,
  item: (caseRef: string, ref: string) => ['correlations', caseRef, 'item', ref] as const,
}

export const useCorrelations = (caseRef: string | null, query: CorrelationQuery = {}) =>
  useQuery({
    queryKey: correlationKeys.list(caseRef ?? 'none', query),
    queryFn: () => CorrelationService.list(caseRef as string, query),
    enabled: caseRef !== null,
    placeholderData: keepPreviousData,
  })

export const useCorrelation = (caseRef: string, ref: string) =>
  useQuery({ queryKey: correlationKeys.item(caseRef, ref), queryFn: () => CorrelationService.get(caseRef, ref) })

const refreshCorrelations = (caseRef: string) =>
  Promise.all([
    queryClient.invalidateQueries({ queryKey: correlationKeys.all(caseRef) }),
    queryClient.invalidateQueries({ queryKey: ['graph', caseRef] }),
    queryClient.invalidateQueries({ queryKey: queryKeys.investigations }),
  ])

export const useRunCorrelation = (caseRef: string) =>
  useMutation({ mutationFn: () => CorrelationService.run(caseRef), onSuccess: () => refreshCorrelations(caseRef) })

export const useReviewCorrelation = (caseRef: string, ref: string) =>
  useMutation({
    mutationFn: ({ status, note }: { status: ReviewStatus; note?: string }) =>
      CorrelationService.review(caseRef, ref, status, note),
    onSuccess: () => refreshCorrelations(caseRef),
  })

// ---------- Relationship graph -----------------------------------------------------------

export const useGraph = (caseRef: string | null, query: GraphQuery = {}) =>
  useQuery({
    queryKey: ['graph', caseRef ?? 'none', query] as const,
    queryFn: () => GraphService.get(caseRef as string, query),
    enabled: caseRef !== null,
    placeholderData: keepPreviousData,
  })

// ---------- AI (local, Ollama) ----------------------------------------------------------

export const useAIStatus = () =>
  useQuery({ queryKey: ['ai', 'status'], queryFn: AIService.status, staleTime: 30_000, retry: false })

export const useAISearch = (caseRef: string) =>
  useMutation({ mutationFn: (question: string) => AIService.search(caseRef, question) })

export const useSimilarEvidence = (caseRef: string, evidenceRef: string) =>
  useQuery({ queryKey: ['similar', caseRef, evidenceRef], queryFn: () => AIService.similar(caseRef, evidenceRef) })

export const useReindex = (caseRef: string) =>
  useMutation({
    mutationFn: () => AIService.reindex(caseRef),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['similar', caseRef] }),
  })
