import { Outlet } from 'react-router-dom'
import { ThreadSidebar } from '@/components/chat/ThreadSidebar'

export function AppLayout() {
  return (
    <div className="flex h-svh bg-background text-foreground">
      <ThreadSidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <Outlet />
      </div>
    </div>
  )
}
