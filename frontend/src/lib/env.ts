// Single source of truth for client env vars, validated once at boot.
// Never read `import.meta.env.X` anywhere else — import `env` from here.
// Only VITE_-prefixed vars are exposed to the browser; keep secrets out.

function required(name: string, value: string | undefined): string {
  if (!value) {
    throw new Error(
      `Missing required env var ${name}. Add it to frontend/.env (see .env.example).`,
    )
  }
  return value
}

export const env = {
  // Empty = same origin. In the Docker deploy the API is served from the same
  // host as the SPA, so no base URL is needed. Set VITE_API_BASE_URL only when
  // the backend lives on a different origin (e.g. separate local dev server).
  API_BASE_URL: import.meta.env.VITE_API_BASE_URL ?? '',
  SUPABASE_URL: required('VITE_SUPABASE_URL', import.meta.env.VITE_SUPABASE_URL),
  SUPABASE_ANON_KEY: required(
    'VITE_SUPABASE_ANON_KEY',
    import.meta.env.VITE_SUPABASE_ANON_KEY,
  ),
} as const
