import { env } from '@/lib/env'

// Thin wrapper over the native fetch API. No axios/ky/got — see AGENTS.md.
// Handles base URL, JSON, timeouts, and typed errors. Auth is layered on top
// in @/lib/api; this module stays auth-agnostic.

const DEFAULT_TIMEOUT_MS = 30_000

export interface RequestOptions {
  method?: string
  // Plain object → JSON-encoded. Omit for GET/DELETE without a body.
  body?: unknown
  headers?: Record<string, string>
  // Caller-supplied abort signal, combined with the internal timeout.
  signal?: AbortSignal
  timeoutMs?: number
}

// Every failure from the api layer is an ApiError, so callers only catch one type.
export class ApiError extends Error {
  readonly status: number
  readonly body: unknown
  // true = fetch itself failed (network down, CORS, DNS, timeout) — no HTTP
  // response was received. false = the server responded with a non-2xx status.
  readonly isNetworkError: boolean

  constructor(
    message: string,
    opts: { status: number; body: unknown; isNetworkError: boolean; cause?: unknown },
  ) {
    super(message, { cause: opts.cause })
    this.name = 'ApiError'
    this.status = opts.status
    this.body = opts.body
    this.isNetworkError = opts.isNetworkError
  }
}

function parseBody(text: string): unknown {
  if (!text) return undefined
  try {
    return JSON.parse(text)
  } catch {
    // Non-JSON response (e.g. an HTML error page) — hand back the raw text.
    return text
  }
}

export async function request<T>(
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  const {
    method = 'GET',
    body,
    headers = {},
    signal,
    timeoutMs = DEFAULT_TIMEOUT_MS,
  } = options

  const url = /^https?:\/\//.test(path) ? path : `${env.API_BASE_URL}${path}`

  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), timeoutMs)
  const onAbort = () => controller.abort()
  signal?.addEventListener('abort', onAbort)

  const finalHeaders: Record<string, string> = { Accept: 'application/json', ...headers }
  let payload: string | undefined
  if (body !== undefined) {
    finalHeaders['Content-Type'] = 'application/json'
    payload = JSON.stringify(body)
  }

  let response: Response
  try {
    response = await fetch(url, {
      method,
      headers: finalHeaders,
      body: payload,
      signal: controller.signal,
    })
  } catch (cause) {
    const timedOut = cause instanceof Error && cause.name === 'AbortError'
    throw new ApiError(
      timedOut
        ? `Request to ${path} timed out after ${timeoutMs}ms`
        : `Network request to ${path} failed`,
      { status: 0, body: undefined, isNetworkError: true, cause },
    )
  } finally {
    clearTimeout(timeout)
    signal?.removeEventListener('abort', onAbort)
  }

  const data = parseBody(await response.text())

  if (!response.ok) {
    throw new ApiError(`Request to ${path} failed with status ${response.status}`, {
      status: response.status,
      body: data,
      isNetworkError: false,
    })
  }

  return data as T
}
