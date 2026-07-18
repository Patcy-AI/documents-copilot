import { useParams } from 'react-router-dom'
import { useChatStream } from '@/hooks/useChatStream'
import { MessageList } from '@/components/chat/MessageList'
import { Composer } from '@/components/chat/Composer'

export function ChatPage() {
  const { threadId } = useParams()
  // Remount on thread change so the hook re-initializes cleanly.
  return <ChatThread key={threadId} threadId={threadId!} />
}

function ChatThread({ threadId }: { threadId: string }) {
  const { messages, loading, sending, send } = useChatStream(threadId)

  return (
    <>
      {loading ? (
        <div className="flex flex-1 items-center justify-center text-muted-foreground">
          Loading…
        </div>
      ) : (
        <MessageList messages={messages} sending={sending} />
      )}
      <Composer onSend={send} disabled={sending || loading} />
    </>
  )
}
