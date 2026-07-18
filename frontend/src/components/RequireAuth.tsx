import { Navigate, Outlet } from 'react-router-dom'
import { useSession } from '@/hooks/useSession'

// Route guard: renders child routes only for signed-in users. Redirects to
// /login otherwise. Waits for the initial session read so we don't bounce a
// logged-in analyst to the login screen on refresh.
export function RequireAuth() {
  const { session, loading } = useSession()

  if (loading) {
    return (
      <div className="min-h-svh grid place-items-center text-muted-foreground">
        Loading…
      </div>
    )
  }

  if (!session) {
    return <Navigate to="/login" replace />
  }

  return <Outlet />
}
