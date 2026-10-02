/**
 * InvestigationService (plan §49) — now backed by the real API.
 * Screens call these functions; they never see HTTP or snake_case.
 */
import type {
  AssignableUserDto,
  AuditEntryDto,
  InvestigationCreateDto,
  InvestigationDto,
  InvestigationPageDto,
  InvestigationUpdateDto,
  MemberDto,
} from '@/api/types'
import type {
  AuditEntry,
  Investigation,
  InvestigationMember,
  InvestigationStatus,
  Priority,
  Role,
} from '@/domain/types'
import { apiGet, apiPatch, apiPost } from './apiClient'

export interface InvestigationQuery {
  search?: string
  status?: InvestigationStatus
  priority?: Priority
  limit?: number
  offset?: number
}

export interface InvestigationPage {
  items: Investigation[]
  total: number
  limit: number
  offset: number
}

export interface NewInvestigation {
  title: string
  caseType: string
  priority: Priority
  location: string
  description: string
  tags: string[]
}

export type InvestigationChanges = Partial<
  Pick<Investigation, 'title' | 'caseType' | 'priority' | 'status' | 'stage' | 'location' | 'description' | 'tags'>
>

const toInvestigation = (dto: InvestigationDto): Investigation => ({
  reference: dto.reference,
  title: dto.title,
  description: dto.description,
  caseType: dto.case_type,
  status: dto.status,
  priority: dto.priority,
  stage: dto.stage,
  location: dto.location,
  tags: dto.tags,
  leadInvestigator: { id: dto.lead_investigator.id, displayName: dto.lead_investigator.display_name },
  teamSize: dto.team_size,
  myRoleInCase: dto.my_role_in_case ?? null,
  counts: dto.counts,
  createdAt: dto.created_at,
  updatedAt: dto.updated_at,
})

const toMember = (dto: MemberDto): InvestigationMember => ({
  userId: dto.user_id,
  displayName: dto.display_name,
  email: dto.email,
  role: dto.role as Role,
  roleInCase: dto.role_in_case,
  addedAt: dto.added_at,
})

const toAuditEntry = (dto: AuditEntryDto): AuditEntry => ({
  id: dto.id,
  occurredAt: dto.occurred_at,
  actorEmail: dto.actor_email ?? null,
  action: dto.action,
  previousState: (dto.previous_state as Record<string, unknown> | null) ?? null,
  newState: (dto.new_state as Record<string, unknown> | null) ?? null,
  note: dto.note ?? null,
})

function queryString(query: InvestigationQuery): string {
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(query)) {
    if (value !== undefined && value !== '') params.set(key, String(value))
  }
  const text = params.toString()
  return text ? `?${text}` : ''
}

export const InvestigationService = {
  async list(query: InvestigationQuery = {}): Promise<InvestigationPage> {
    const page = await apiGet<InvestigationPageDto>(`/investigations${queryString(query)}`)
    return { ...page, items: page.items.map(toInvestigation) }
  },

  async get(reference: string): Promise<Investigation> {
    return toInvestigation(await apiGet<InvestigationDto>(`/investigations/${encodeURIComponent(reference)}`))
  },

  async create(input: NewInvestigation): Promise<Investigation> {
    const body: InvestigationCreateDto = {
      title: input.title,
      case_type: input.caseType,
      priority: input.priority,
      location: input.location,
      description: input.description,
      tags: input.tags,
    }
    return toInvestigation(await apiPost<InvestigationDto>('/investigations', body))
  },

  async update(reference: string, changes: InvestigationChanges): Promise<Investigation> {
    const body: InvestigationUpdateDto = {
      ...(changes.title !== undefined && { title: changes.title }),
      ...(changes.caseType !== undefined && { case_type: changes.caseType }),
      ...(changes.priority !== undefined && { priority: changes.priority }),
      ...(changes.status !== undefined && { status: changes.status }),
      ...(changes.stage !== undefined && { stage: changes.stage }),
      ...(changes.location !== undefined && { location: changes.location }),
      ...(changes.description !== undefined && { description: changes.description }),
      ...(changes.tags !== undefined && { tags: changes.tags }),
    }
    return toInvestigation(
      await apiPatch<InvestigationDto>(`/investigations/${encodeURIComponent(reference)}`, body),
    )
  },

  async members(reference: string): Promise<InvestigationMember[]> {
    const members = await apiGet<MemberDto[]>(`/investigations/${encodeURIComponent(reference)}/members`)
    return members.map(toMember)
  },

  async addMember(reference: string, email: string): Promise<InvestigationMember> {
    return toMember(
      await apiPost<MemberDto>(`/investigations/${encodeURIComponent(reference)}/members`, { email }),
    )
  },

  async activity(reference: string): Promise<AuditEntry[]> {
    const rows = await apiGet<AuditEntryDto[]>(`/investigations/${encodeURIComponent(reference)}/activity`)
    return rows.map(toAuditEntry)
  },

  async assignableUsers(): Promise<{ id: string; displayName: string; email: string; role: Role }[]> {
    const users = await apiGet<AssignableUserDto[]>('/investigations/assignable-users')
    return users.map((u) => ({ id: u.id, displayName: u.display_name, email: u.email, role: u.role as Role }))
  },
}
