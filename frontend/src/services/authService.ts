import type { CurrentUser, Permission, Role } from '@/domain/types'
import { ApiError, apiGet, apiPost } from './apiClient'

/** Shape sent by the API (snake_case, backend/app/api/schemas.py). */
interface CurrentUserDto {
  id: string
  email: string
  display_name: string
  role: Role
  permissions: Permission[]
  mfa_enabled: boolean
  session_expires_at: string
}

const toCurrentUser = (dto: CurrentUserDto): CurrentUser => ({
  id: dto.id,
  email: dto.email,
  displayName: dto.display_name,
  role: dto.role,
  permissions: dto.permissions,
  mfaEnabled: dto.mfa_enabled,
  sessionExpiresAt: dto.session_expires_at,
})

export interface LoginInput {
  email: string
  password: string
  remember: boolean
}

export const AuthService = {
  /** The signed-in user, or null when there is no valid session. */
  async me(): Promise<CurrentUser | null> {
    try {
      return toCurrentUser(await apiGet<CurrentUserDto>('/auth/me'))
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) return null
      throw error
    }
  },

  async login(input: LoginInput): Promise<CurrentUser> {
    return toCurrentUser(await apiPost<CurrentUserDto>('/auth/login', input))
  },

  async logout(): Promise<void> {
    await apiPost<void>('/auth/logout')
  },
}

export function can(user: CurrentUser | null | undefined, permission: Permission): boolean {
  return user?.permissions.includes(permission) ?? false
}
