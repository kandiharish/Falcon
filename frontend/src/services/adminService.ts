import type { Role, UserSummary } from '@/domain/types'
import { apiGet } from './apiClient'

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

export const AdminService = {
  async listUsers(): Promise<UserSummary[]> {
    const users = await apiGet<UserSummaryDto[]>('/admin/users')
    return users.map((u) => ({
      id: u.id,
      email: u.email,
      displayName: u.display_name,
      role: u.role,
      isActive: u.is_active,
      mfaEnabled: u.mfa_enabled,
      locked: u.locked,
      lastLoginAt: u.last_login_at,
      createdAt: u.created_at,
    }))
  },
}
