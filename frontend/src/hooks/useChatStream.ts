import { useCallback, useEffect, useState } from 'react'
import { loadMessages, streamChat } from '@/lib/chat'

export interface UiMessage {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
}

// Owns one thread's messages: loads history, then streams the assistant reply
// into the last message as deltas arrive. Resets when threadId changes.
export function useChatStream(threadId: string) {
  const [messages, setMessages] = useState<UiMessage[]>([])
  const [loading, setLoading] = useState(true)
  const [sending, setSending] = useState(false)

  useEffect(() => {
    let active = true
    setLoading(true)
    loadMessages(threadId)
      .then((history) => {
        if (active) {
          setMessages(
            history.map((m) => ({ id: m.id, role: m.role, content: m.content })),
          )
        }
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => {
      active = false
    }
  }, [threadId])

  const send = useCallback(
    async (text: string) => {
      const assistantId = crypto.randomUUID()
      setSending(true)
      setMessages((prev) => [
        ...prev,
        { id: crypto.randomUUID(), role: 'user', content: text },
        { id: assistantId, role: 'assistant', content: '' },
      ])
      try {
        await streamChat(threadId, text, (delta) => {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId ? { ...m, content: m.content + delta } : m,
            ),
          )
        })
      } finally {
        setSending(false)
      }
    },
    [threadId],
  )

  return { messages, loading, sending, send }
}
