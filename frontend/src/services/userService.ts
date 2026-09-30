import type { CurrentUser } from '@/domain/types'
import { MOCK_CURRENT_USER } from './mock/fixtures'
import { simulateLatency } from './mock/latency'

/** UserService — Phase 2 mock; Phase 3 reads the signed-in user from the session. */
export const UserService = {
  async getCurrentUser(): Promise<CurrentUser> {
    await simulateLatency(100)
    return MOCK_CURRENT_USER
  },
}
