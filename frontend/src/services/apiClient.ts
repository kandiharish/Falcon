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

type Method = 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'

async function request<T>(method: Method, path: string, body?: unknown): Promise<T> {
  let response: Response
  try {
    response = await fetch(`/api${path}`, {
      method,
      credentials: 'same-origin', // send the httpOnly session cookie
      headers: {
        Accept: 'application/json',
        // CSRF defence: other websites cannot add this header to requests aimed at FALCON.
        'X-FALCON-Request': '1',
        ...(body !== undefined ? { 'Content-Type': 'application/json' } : {}),
      },
      body: body !== undefined ? JSON.stringify(body) : undefined,
    })
  } catch {
    throw new ApiError(0, UNREACHABLE_MESSAGE)
  }

  if (GATEWAY_STATUSES.has(response.status)) {
    throw new ApiError(response.status, UNREACHABLE_MESSAGE)
  }
  if (!response.ok) {
    throw new ApiError(response.status, await readErrorMessage(response))
  }
  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

/** The API sends human-readable messages in `detail`; fall back to a generic one. */
async function readErrorMessage(response: Response): Promise<string> {
  try {
    const data = (await response.json()) as { detail?: unknown }
    if (typeof data.detail === 'string') return data.detail
  } catch {
    // not JSON
  }
  return `The request could not be completed (code ${response.status}). Try again in a moment.`
}

export const apiGet = <T>(path: string) => request<T>('GET', path)
export const apiPost = <T>(path: string, body?: unknown) => request<T>('POST', path, body)
export const apiPatch = <T>(path: string, body: unknown) => request<T>('PATCH', path, body)

/**
 * Upload a form with a file and report progress (0–100).
 * fetch() cannot report upload progress, so this one uses XMLHttpRequest.
 */
export function apiUpload<T>(path: string, form: FormData, onProgress?: (percent: number) => void): Promise<T> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    xhr.open('POST', `/api${path}`)
    xhr.withCredentials = true
    xhr.setRequestHeader('X-FALCON-Request', '1')
    xhr.setRequestHeader('Accept', 'application/json')
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable && onProgress) onProgress(Math.round((100 * event.loaded) / event.total))
    }
    xhr.onerror = () => reject(new ApiError(0, UNREACHABLE_MESSAGE))
    xhr.onload = () => {
      if (GATEWAY_STATUSES.has(xhr.status)) return reject(new ApiError(xhr.status, UNREACHABLE_MESSAGE))
      let body: unknown = null
      try {
        body = JSON.parse(xhr.responseText)
      } catch {
        // not JSON
      }
      if (xhr.status >= 200 && xhr.status < 300) return resolve(body as T)
      const detail = (body as { detail?: unknown } | null)?.detail
      reject(
        new ApiError(
          xhr.status,
          typeof detail === 'string'
            ? detail
            : xhr.status === 413
              ? 'The file is too large to upload.'
              : `The upload could not be completed (code ${xhr.status}). Try again.`,
        ),
      )
    }
    xhr.send(form)
  })
}
