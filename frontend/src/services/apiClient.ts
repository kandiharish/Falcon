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

  await throwIfFailed(response)
  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

async function throwIfFailed(response: Response): Promise<void> {
  if (response.ok) return
  const detail = await readDetail(response)
  // A 503 WITH a message comes from FALCON itself (e.g. "start the local AI service");
  // without one it comes from the proxy: the API is down.
  if (GATEWAY_STATUSES.has(response.status)) throw new ApiError(response.status, detail ?? UNREACHABLE_MESSAGE)
  throw new ApiError(
    response.status,
    detail ?? `The request could not be completed (code ${response.status}). Try again in a moment.`,
  )
}

/** The API sends human-readable messages in `detail`. */
async function readDetail(response: Response): Promise<string | null> {
  try {
    const data = (await response.json()) as { detail?: unknown }
    if (typeof data.detail === 'string') return data.detail
  } catch {
    // not JSON
  }
  return null
}

export const apiGet = <T>(path: string) => request<T>('GET', path)
export const apiPost = <T>(path: string, body?: unknown) => request<T>('POST', path, body)
export const apiPatch = <T>(path: string, body: unknown) => request<T>('PATCH', path, body)
export const apiDelete = (path: string) => request<void>('DELETE', path)

/**
 * POST, then read a streamed reply of newline-delimited JSON (NDJSON) as it arrives:
 * each complete line is one event. Used by the Investigation Assistant, which can take
 * minutes on a CPU and reports every step while it works.
 */
export async function* apiStream<E>(path: string, body: unknown, signal?: AbortSignal): AsyncGenerator<E> {
  let response: Response
  try {
    response = await fetch(`/api${path}`, {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'X-FALCON-Request': '1', 'Content-Type': 'application/json', Accept: 'application/x-ndjson' },
      body: JSON.stringify(body),
      signal,
    })
  } catch (error) {
    if (signal?.aborted) return
    throw error instanceof ApiError ? error : new ApiError(0, UNREACHABLE_MESSAGE)
  }
  await throwIfFailed(response)
  if (!response.body) return
  const reader = response.body.pipeThrough(new TextDecoderStream()).getReader()
  let buffer = ''
  while (true) {
    const { value, done } = await reader.read()
    if (done) break
    buffer += value
    let newline = buffer.indexOf('\n')
    while (newline >= 0) {
      const line = buffer.slice(0, newline).trim()
      buffer = buffer.slice(newline + 1)
      if (line) yield JSON.parse(line) as E
      newline = buffer.indexOf('\n')
    }
  }
  if (buffer.trim()) yield JSON.parse(buffer) as E
}

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
