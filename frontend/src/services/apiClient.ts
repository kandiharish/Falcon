/**
 * The single place that talks HTTP to the FALCON API.
 * Services call this; UI components never call fetch() directly.
 */

export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

const UNREACHABLE_MESSAGE =
  'The FALCON server could not be reached. Check that the backend is running, then try again.'

// 502/503/504 come from the proxy in front of the API: the API itself is down or not answering.
const GATEWAY_STATUSES = new Set([502, 503, 504])

export async function apiGet<T>(path: string): Promise<T> {
  let response: Response
  try {
    response = await fetch(`/api${path}`, { headers: { Accept: 'application/json' } })
  } catch {
    throw new ApiError(0, UNREACHABLE_MESSAGE)
  }

  if (GATEWAY_STATUSES.has(response.status)) {
    throw new ApiError(response.status, UNREACHABLE_MESSAGE)
  }
  if (!response.ok) {
    throw new ApiError(
      response.status,
      `The request could not be completed (code ${response.status}). Try again in a moment.`,
    )
  }
  return (await response.json()) as T
}
