import type { AuditPageDto } from '@/api/types'
import type { AuditEntry, Role, UserSummary } from '@/domain/types'
import { apiGet, apiPatch, apiPost } from './apiClient'

interface UserSummaryDto {
  id: string
  email: string
  display_name: string
  role: Role
  is_active: boolean
  mfa_enabled: boolean
  locked: boolean
  last_login_at: string | null
  created_at: string
}

export interface AuditQuery {
  action?: string
  actor?: string
  object?: string
  date_from?: string
  date_to?: string
  limit?: number
  offset?: number
}

const toUser = (u: UserSummaryDto): UserSummary => ({
  id: u.id,
  email: u.email,
  displayName: u.display_name,
  role: u.role,
  isActive: u.is_active,
  mfaEnabled: u.mfa_enabled,
  locked: u.locked,
  lastLoginAt: u.last_login_at,
  createdAt: u.created_at,
})

export function auditQueryString(query: AuditQuery): string {
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(query)) if (value !== undefined && value !== '') params.set(key, String(value))
  const text = params.toString()
  return text ? `?${text}` : ''
}

export const AdminService = {
  async listUsers(): Promise<UserSummary[]> {
    return (await apiGet<UserSummaryDto[]>('/admin/users')).map(toUser)
  },
  async createUser(input: { email: string; display_name: string; role: Role; temporary_password: string }): Promise<UserSummary> {
    return toUser(await apiPost<UserSummaryDto>('/admin/users', input))
  },
  async updateUser(id: string, input: { display_name?: string; role?: Role; is_active?: boolean }): Promise<UserSummary> {
    return toUser(await apiPatch<UserSummaryDto>(`/admin/users/${id}`, input))
  },
  async unlock(id: string): Promise<UserSummary> {
    return toUser(await apiPost<UserSummaryDto>(`/admin/users/${id}/unlock`))
  },
  async resetMfa(id: string): Promise<UserSummary> {
    return toUser(await apiPost<UserSummaryDto>(`/admin/users/${id}/reset-mfa`))
  },
  async resetPassword(id: string, temporaryPassword: string): Promise<UserSummary> {
    return toUser(await apiPost<UserSummaryDto>(`/admin/users/${id}/password`, { temporary_password: temporaryPassword }))
  },
  async audit(query: AuditQuery): Promise<{ items: AuditEntry[]; total: number }> {
    const page = await apiGet<AuditPageDto>(`/audit${auditQueryString(query)}`)
    return {
      total: page.total,
      items: page.items.map((a) => ({
        id: a.id,
        occurredAt: a.occurred_at,
        actorEmail: a.actor_email ?? null,
        action: a.action,
        objectType: a.object_type ?? null,
        objectId: a.object_id ?? null,
        ipAddress: a.ip_address ?? null,
        previousState: (a.previous_state as Record<string, unknown> | null) ?? null,
        newState: (a.new_state as Record<string, unknown> | null) ?? null,
        note: a.note ?? null,
      })),
    }
  },
}
