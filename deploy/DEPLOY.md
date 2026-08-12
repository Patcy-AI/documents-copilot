# Deploying Document Copilot

The whole app ships as **one Docker image**: the React frontend is built and
served from the same FastAPI server, so there's a single public URL and no CORS
to configure. It's built for **Hugging Face Spaces** (Docker SDK), which gives a
free container with enough RAM (16 GB) for the local embedding model + torch —
free micro-tiers like Render's 512 MB can't fit those.

The corpus is already ingested into Supabase (document_chunks), so nothing needs
to be re-embedded — this just stands the app up in front of that data.

---

## What you'll need

- A Hugging Face account (free): https://huggingface.co/join
- Your Supabase project values (Dashboard → Project Settings):
  - `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY` (API page)
  - `DATABASE_URL` — the **direct** connection (host `db.<ref>.supabase.co:5432`),
    not the pooler
- An Anthropic API key: https://console.anthropic.com → API Keys

---

## Step 1 — Create the Space

1. Go to https://huggingface.co/new-space
2. Name it (e.g. `document-copilot`), License: your choice.
3. **Space SDK: Docker** → **Blank** template.
4. Choose the free CPU hardware. Create the Space.

## Step 2 — Push the code to the Space

The Space is its own git repo. From your local clone of the project:

```bash
git remote add space https://huggingface.co/spaces/<your-hf-username>/document-copilot
git push space main
```

(If your default branch is `main`, that's it. HF builds from the `Dockerfile`
at the repo root automatically.)

## Step 3 — Add the Space front-matter

Hugging Face needs a few config lines at the very top of the Space's
`README.md`. The block is in `deploy/SPACE_README.md`. Easiest way:

- Open the Space → **Files** → edit `README.md` in the web editor, and paste the
  block from `deploy/SPACE_README.md` at the very top (above everything else),
  then commit. The Space will rebuild.

The important lines are `sdk: docker` and `app_port: 7860`.

## Step 4 — Set the environment

In the Space → **Settings** → **Variables and secrets**:

**Secrets** (backend, private — kept server-side):

| Name | Value |
|------|-------|
| `ANTHROPIC_API_KEY` | your Anthropic key |
| `ANTHROPIC_MODEL` | `claude-sonnet-5` (or `claude-opus-5` for top quality) |
| `SUPABASE_URL` | `https://<ref>.supabase.co` |
| `SUPABASE_ANON_KEY` | your anon key |
| `SUPABASE_SERVICE_ROLE_KEY` | your service-role key |
| `DATABASE_URL` | direct Postgres URL (URL-encode any special chars in the password) |
| `ALLOWED_ORIGINS` | your Space URL, e.g. `https://<user>-document-copilot.hf.space` |

**Variables** (frontend, public — baked into the browser bundle at build time):

| Name | Value |
|------|-------|
| `VITE_SUPABASE_URL` | `https://<ref>.supabase.co` |
| `VITE_SUPABASE_ANON_KEY` | your anon key |

> The Supabase anon key is safe to expose — it's protected by row-level
> security. The service-role key is **not**; keep it in Secrets only.

After adding these, trigger a rebuild (Settings → **Factory rebuild**), since the
frontend build reads the Variables at build time.

## Step 5 — Point Supabase auth at the Space

So email login redirects back to the deployed app:

- Supabase Dashboard → **Authentication** → **URL Configuration**
- Set **Site URL** to your Space URL, and add it under **Redirect URLs** too.

## Step 6 — Verify

Open the Space URL and check:

1. `‹space-url›/health` returns `{"status":"ok"}`.
2. Log in with email, start a thread.
3. Ask an **in-corpus** question, e.g.
   *"How did NVIDIA describe Data Center demand drivers in its fiscal 2025 10-K?"*
   → you should get an answer with a **Sources** panel citing the filing, and
   each source expands to show the exact passage.
4. Ask an **out-of-corpus** question, e.g.
   *"What is Tesla's 2025 revenue?"* or *"Who won the 2026 Super Bowl?"*
   → it should **refuse** and say it only covers the five companies' 10-Ks.

That refusal + the citations are the whole trust story — good things to capture
on camera.

---

## Notes

- **First request is slow.** On the first question the server downloads the
  embedding model (~130 MB) and loads it into memory. That's a one-time warm-up;
  subsequent questions are fast. Ask one throwaway question before you start
  recording so the model is already loaded.
- **Model id.** `ANTHROPIC_MODEL` must be a valid public API model id. As of this
  writing: `claude-opus-5`, `claude-sonnet-5`, `claude-haiku-4-5`. If answers
  fail with a model error, that's the value to check.
- **Running elsewhere.** The image is a standard Docker container — it runs on
  any host with enough RAM (Fly.io, Railway, a VPS). Only the env-var UI differs.
- **Split hosting (optional).** If you ever host the API and frontend on separate
  origins, set `VITE_API_BASE_URL` to the API's URL at build time and put the
  frontend origin in `ALLOWED_ORIGINS`. The default (empty) assumes same-origin,
  which is what this single-image deploy uses.
