import { getAccessToken } from '@/lib/auth'
import { request, type RequestOptions } from '@/lib/http'

// The singleton every component/page uses to talk to the Python backend.
// It injects the Supabase bearer token automatically — never thread tokens
// through props or set the Authorization header by hand.

// Per-call options, minus the parts the verb + api layer control.
type CallOptions = Omit<RequestOptions, 'method' | 'body'>

async function authHeaders(): Promise<Record<string, string>> {
  const token = await getAccessToken()
  return token ? { Authorization: `Bearer ${token}` } : {}
}

async function send<T>(
  method: string,
  path: string,
  body?: unknown,
  options: CallOptions = {},
): Promise<T> {
  const auth = await authHeaders()
  return request<T>(path, {
    ...options,
    method,
    body,
    // Caller headers win over the injected auth header if they collide.
    headers: { ...auth, ...options.headers },
  })
}

export const api = {
  get: <T>(path: string, options?: CallOptions) => send<T>('GET', path, undefined, options),
  post: <T>(path: string, body?: unknown, options?: CallOptions) =>
    send<T>('POST', path, body, options),
  put: <T>(path: string, body?: unknown, options?: CallOptions) =>
    send<T>('PUT', path, body, options),
  patch: <T>(path: string, body?: unknown, options?: CallOptions) =>
    send<T>('PATCH', path, body, options),
  delete: <T>(path: string, options?: CallOptions) =>
    send<T>('DELETE', path, undefined, options),
}
