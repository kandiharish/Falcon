import type { CurrentUser, Permission, Role } from '@/domain/types'
import { ApiError, apiDelete, apiGet, apiPost } from './apiClient'

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

interface SessionDto {
  id: string
  created_at: string
  last_seen_at: string
  expires_at: string
  ip_address?: string | null
  user_agent?: string | null
  current: boolean
}

export interface AccountSession {
  id: string
  createdAt: string
  lastSeenAt: string
  expiresAt: string
  ipAddress: string | null
  userAgent: string | null
  current: boolean
}

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

  /** Step 1. With MFA on, `user` stays null until verifyCode() succeeds. */
  async login(input: LoginInput): Promise<{ mfaRequired: boolean; user: CurrentUser | null }> {
    const result = await apiPost<{ mfa_required: boolean; user: CurrentUserDto | null }>('/auth/login', input)
    return { mfaRequired: result.mfa_required, user: result.user ? toCurrentUser(result.user) : null }
  },

  /** Step 2: the 6-digit code from the authenticator app, or a recovery code. */
  async verifyCode(code: string): Promise<CurrentUser> {
    return toCurrentUser(await apiPost<CurrentUserDto>('/auth/mfa/verify', { code }))
  },

  mfaSetup: () => apiPost<{ secret: string; uri: string; qr_svg: string }>('/auth/mfa/setup'),
  mfaConfirm: (code: string) => apiPost<{ recovery_codes: string[] }>('/auth/mfa/confirm', { code }),
  mfaDisable: (password: string, code: string) => apiPost<void>('/auth/mfa/disable', { password, code }),

  async sessions(): Promise<AccountSession[]> {
    const rows = await apiGet<SessionDto[]>('/auth/sessions')
    return rows.map((s) => ({
      id: s.id,
      createdAt: s.created_at,
      lastSeenAt: s.last_seen_at,
      expiresAt: s.expires_at,
      ipAddress: s.ip_address ?? null,
      userAgent: s.user_agent ?? null,
      current: s.current,
    }))
  },
  endSession: (id: string) => apiDelete(`/auth/sessions/${id}`),

  async logout(): Promise<void> {
    await apiPost<void>('/auth/logout')
  },
}

export function can(user: CurrentUser | null | undefined, permission: Permission): boolean {
  return user?.permissions.includes(permission) ?? false
}
