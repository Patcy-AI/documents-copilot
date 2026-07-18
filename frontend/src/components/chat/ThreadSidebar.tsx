import { useEffect, useState } from 'react'
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom'
import { createThread, listThreads, type Thread } from '@/lib/chat'
import { signOut } from '@/lib/auth'
import { useSession } from '@/hooks/useSession'
import { Button } from '@/components/ui/button'

export function ThreadSidebar() {
  const navigate = useNavigate()
  const location = useLocation()
  const { threadId } = useParams()
  const { session } = useSession()
  const [threads, setThreads] = useState<Thread[]>([])

  // Refetch on navigation so a newly created thread shows up in the list.
  useEffect(() => {
    let active = true
    listThreads().then((t) => {
      if (active) setThreads(t)
    })
    return () => {
      active = false
    }
  }, [location.pathname])

  async function handleNewChat() {
    const thread = await createThread()
    navigate(`/chat/${thread.id}`)
  }

  async function handleSignOut() {
    await signOut()
    navigate('/login', { replace: true })
  }

  return (
    <aside className="flex h-svh w-64 shrink-0 flex-col border-r bg-muted/30">
      <div className="p-3">
        <Button className="w-full" onClick={handleNewChat}>
          New chat
        </Button>
      </div>
      <nav className="flex-1 overflow-y-auto px-2">
        {threads.map((t) => (
          <Link
            key={t.id}
            to={`/chat/${t.id}`}
            className={`block truncate rounded-md px-3 py-2 text-sm ${
              t.id === threadId
                ? 'bg-accent text-accent-foreground'
                : 'text-muted-foreground hover:bg-accent/50'
            }`}
          >
            {t.title ?? 'Untitled chat'}
          </Link>
        ))}
        {threads.length === 0 && (
          <p className="px-3 py-2 text-sm text-muted-foreground">
            No conversations yet.
          </p>
        )}
      </nav>
      <div className="border-t p-3">
        <p className="mb-2 truncate text-xs text-muted-foreground">
          {session?.user.email}
        </p>
        <Button variant="outline" size="sm" className="w-full" onClick={handleSignOut}>
          Sign out
        </Button>
      </div>
    </aside>
  )
}
