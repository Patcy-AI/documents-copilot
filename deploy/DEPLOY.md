# Deploying Document Copilot

The whole app ships as **one container**: the React frontend is built and served
by the FastAPI backend, so there's a single public URL and no CORS to configure.
It's deployed on **Google Cloud Run** — a serverless container host with enough
memory for the local embedding model + torch, a usable free tier, and no servers
to manage (a good fit for the brief's "no infra team" constraint).

The corpus is already ingested into Supabase (`document_chunks`), so nothing is
re-embedded here — this just stands the app up in front of that data.

> The reference design in `docs/architecture.md` describes two Railway services.
> We deploy the same app as a single Cloud Run container instead; the code serves
> the SPA and the API from one origin (`backend/app/main.py`).

---

## What you need

- The **gcloud CLI**: https://cloud.google.com/sdk/docs/install (needs Python 3.10–3.14).
- A **GCP project** with billing enabled.
- Your Supabase values and an Anthropic API key (already in `backend/.env`).

## 1. Point gcloud at a project

```bash
gcloud projects create <your-project-id> --name="Document Copilot"   # or reuse one
gcloud config set project <your-project-id>
gcloud billing projects link <your-project-id> --billing-account=<ACCOUNT_ID>
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com
```

## 2. Runtime secrets

The backend reads its secrets from the environment. `deploy/cloudrun.env.yaml`
(git-ignored) holds them for the deploy — it mirrors `backend/.env`:

```yaml
SUPABASE_URL: "https://<ref>.supabase.co"
SUPABASE_ANON_KEY: "sb_publishable_..."
SUPABASE_SERVICE_ROLE_KEY: "..."
DATABASE_URL: "postgresql://...:5432/postgres"
ANTHROPIC_API_KEY: "sk-ant-..."
ANTHROPIC_MODEL: "claude-sonnet-5"
ALLOWED_ORIGINS: "*"
```

`ANTHROPIC_MODEL` must be a valid public API model id (e.g. `claude-sonnet-5`,
`claude-opus-5`, `claude-haiku-4-5`). A wrong id fails every answer at runtime.

## 3. Deploy

From the repo root:

```bash
gcloud run deploy documents-copilot \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --memory 4Gi --cpu 2 --timeout 600 \
  --env-vars-file deploy/cloudrun.env.yaml
```

Cloud Run builds the `Dockerfile` (frontend via pnpm, then the Python backend),
pushes it to Artifact Registry, and returns a public `https://…run.app` URL.
First build takes ~5–8 minutes.

## 4. Point Supabase auth at the URL

Supabase Dashboard → **Authentication → URL Configuration**: set **Site URL** to
your Cloud Run URL and add it under **Redirect URLs**, so email login works.

## 5. Verify

- `‹url›/health` → `{"status":"ok"}`.
- Ask an in-corpus question (e.g. NVIDIA Data Center demand, FY2025) → cited
  answer with a **Sources** panel (filing + SEC Item + the exact passage).
- Ask an out-of-corpus question (e.g. Tesla revenue) → it **refuses** and states
  the corpus it covers.

## Notes

- **First request is slow.** The embedding model (~130 MB) loads on the first
  question, then stays warm. Ask one throwaway question before recording/demoing.
- **Cost.** Cloud Run scales to zero when idle, so an idle demo costs ~nothing;
  you pay only for request time. Delete the service to stop all billing:
  `gcloud run services delete documents-copilot --region us-central1`.
- **Citations.** SEC filings on EDGAR are HTML (no page numbers), so answers cite
  the filing + **SEC Item/section** + the exact passage — the standard, verifiable
  way to locate a claim in a 10-K.
