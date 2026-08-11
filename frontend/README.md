# Document Copilot — Frontend

React + TypeScript SPA (Vite) for Document Copilot. Talks to the FastAPI
backend over JSON; Supabase for email auth. See [AGENTS.md](AGENTS.md) for
conventions.

## Setup

```bash
pnpm install
cp .env.example .env   # fill in VITE_API_BASE_URL and Supabase values
```

## Run

```bash
pnpm dev        # dev server at http://localhost:5173
pnpm build      # production build
pnpm tsc --noEmit && pnpm lint   # typecheck + lint
```

Stack: Vite, React Router, Tailwind, shadcn/ui, `@supabase/supabase-js`.
