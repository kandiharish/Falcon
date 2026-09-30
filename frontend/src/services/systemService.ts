import { apiGet } from './apiClient'

/** Mirrors HealthResponse in backend/app/api/health.py. */
export interface SystemHealth {
  status: 'ok' | 'degraded'
  database: {
    connected: boolean
    server_version: string | null
    extensions: Record<string, string | null>
  }
}

export const SystemService = {
  getHealth: () => apiGet<SystemHealth>('/health'),
}
