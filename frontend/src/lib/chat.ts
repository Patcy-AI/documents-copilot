import { api } from '@/lib/api'
import { env } from '@/lib/env'
import { getAccessToken } from '@/lib/auth'

export interface Citation {
  chunk_id: string
  filing: string
  section?: string | null
  excerpt?: string | null
}

export interface Thread {
  id: string
  title: string | null
  created_at: string
  updated_at: string
}

export interface Message {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  created_at: string
  citations?: Citation[]
}

export function listThreads(): Promise<Thread[]> {
  return api.get<Thread[]>('/chat/threads')
}

export function createThread(title?: string): Promise<Thread> {
  return api.post<Thread>('/chat/threads', { title: title ?? null })
}

export function loadMessages(threadId: string): Promise<Message[]> {
  return api.get<Message[]>(`/chat/threads/${threadId}/messages`)
}

// SSE streaming. Bypasses the `api` client (which parses JSON) to read the raw
// response body; still injects the Supabase bearer token. Every frame's `data:`
// line holds a JSON value: answer deltas are JSON strings (so newlines survive
// the SSE line framing), and the one `event: citations` frame is a JSON array
// of the source passages, sent before the answer streams.
export async function streamChat(
  threadId: string,
  message: string,
  onDelta: (delta: string) => void,
  onCitations?: (citations: Citation[]) => void,
): Promise<void> {
  const token = await getAccessToken()
  const res = await fetch(`${env.API_BASE_URL}/chat/stream`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({ thread_id: threadId, message }),
  })
  if (!res.ok || !res.body) {
    throw new Error(`Stream failed with status ${res.status}`)
  }

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { value, done } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })

    // SSE frames are separated by a blank line; keep any partial trailing frame.
    const frames = buffer.split('\n\n')
    buffer = frames.pop() ?? ''
    for (const frame of frames) {
      let event = 'message'
      let data = ''
      for (const line of frame.split('\n')) {
        if (line.startsWith('event:')) event = line.slice(6).trim()
        else if (line.startsWith('data:')) data = line.slice(5).replace(/^ /, '')
      }
      if (!data) continue

      let parsed: unknown
      try {
        parsed = JSON.parse(data)
      } catch {
        continue // ignore any non-JSON frame (e.g. a comment/keep-alive)
      }

      if (event === 'done') continue
      if (event === 'citations') {
        onCitations?.(parsed as Citation[])
      } else if (typeof parsed === 'string') {
        onDelta(parsed)
      }
    }
  }
}
