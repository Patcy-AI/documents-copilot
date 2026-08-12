import { useEffect, useRef } from 'react'
import type { Citation } from '@/lib/chat'
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
            {m.role === 'assistant' && m.citations && m.citations.length > 0 && (
              <Sources citations={m.citations} />
            )}
          </div>
        ))}
        <div ref={bottomRef} />
      </div>
    </div>
  )
}

// The trust surface: every assistant answer shows the exact filing passages it
// was grounded on, so the analyst can verify a claim in one click.
function Sources({ citations }: { citations: Citation[] }) {
  return (
    <div className="mt-2 flex flex-col gap-1.5">
      <div className="text-xs font-medium text-muted-foreground">Sources</div>
      {citations.map((c, i) => (
        <details
          key={c.chunk_id}
          className="rounded-md border border-border bg-background/50 px-3 py-2 text-xs"
        >
          <summary className="cursor-pointer list-none font-medium text-foreground">
            <span className="text-muted-foreground">[{i + 1}]</span> {c.filing}
            {c.section ? (
              <span className="text-muted-foreground"> — {c.section}</span>
            ) : null}
          </summary>
          {c.excerpt ? (
            <p className="mt-2 whitespace-pre-wrap text-muted-foreground">
              {c.excerpt}
            </p>
          ) : null}
        </details>
      ))}
    </div>
  )
}
