// Empty state shown at "/" before a thread is selected.
export function ChatHome() {
  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-2 text-center">
      <h1 className="text-2xl font-semibold tracking-tight">Document Copilot</h1>
      <p className="text-muted-foreground">
        Start a new chat or pick a conversation from the sidebar.
      </p>
    </div>
  )
}
