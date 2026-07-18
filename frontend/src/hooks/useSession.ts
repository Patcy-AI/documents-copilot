import { useEffect, useState } from 'react'
import type { Session } from '@supabase/supabase-js'
import { getSession, onAuthStateChange } from '@/lib/auth'

// Tracks the current Supabase session. `loading` is true until the initial
// session read resolves, so guards can avoid flashing the login page.
export function useSession() {
  const [session, setSession] = useState<Session | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let active = true

    getSession()
      .then((s) => {
        if (active) setSession(s)
      })
      .catch(() => {
        if (active) setSession(null)
      })
      .finally(() => {
        if (active) setLoading(false)
      })

    // Keep in sync with sign-in / sign-out / token-refresh events.
    const unsubscribe = onAuthStateChange((s) => setSession(s))

    return () => {
      active = false
      unsubscribe()
    }
  }, [])

  return { session, loading }
}
