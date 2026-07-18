import { useEffect, useRef } from 'react'
import type { UiMessage } from '@/hooks/useChatStream'

export function MessageList({
  messages,
  sending,
}: {
  messages: UiMessage[]
  sending: boolean
}) {
  const bottomRef = useRef<HTMLDivElement>(null)

  // Keep the latest message (and streaming deltas) in view.
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="mx-auto flex max-w-2xl flex-col gap-4 p-6">
        {messages.map((m) => (
          <div
            key={m.id}
            className={m.role === 'user' ? 'self-end' : 'self-start'}
          >
            <div
              className={`whitespace-pre-wrap rounded-lg px-4 py-2 text-sm ${
                m.role === 'user'
                  ? 'bg-primary text-primary-foreground'
                  : 'bg-muted text-foreground'
              }`}
            >
              {m.content || (sending ? '…' : '')}
            </div>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>
    </div>
  )
}
