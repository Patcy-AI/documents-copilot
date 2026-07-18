import { createClient } from '@supabase/supabase-js'
import { env } from '@/lib/env'

// Browser Supabase client. Uses only the public anon key (safe to ship to the
// client); the service_role key must never appear in the frontend. Auth is
// email-only for Driftwood analysts — see @/lib/auth for the helpers.
export const supabase = createClient(env.SUPABASE_URL, env.SUPABASE_ANON_KEY, {
  auth: {
    // Keep the analyst signed in across reloads and refresh tokens silently.
    persistSession: true,
    autoRefreshToken: true,
    // Handle the email confirmation / recovery redirect on load.
    detectSessionInUrl: true,
  },
})
