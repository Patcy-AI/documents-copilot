# Document Copilot — single-image deploy.
# Builds the React frontend, then serves it together with the FastAPI backend
# from one origin. Runs on any container host; tuned here for Google Cloud Run
# (listens on $PORT, needs ~2 GiB RAM for the local embedding model + torch).

# ---------- stage 1: build the frontend (pnpm, per frontend/AGENTS.md) ----------
FROM node:22-slim AS frontend
WORKDIR /web
RUN corepack enable && corepack prepare pnpm@latest --activate

# Lockfile + .npmrc first, so the frozen install is cached and the 7-day
# minimum-release-age supply-chain guard in .npmrc is honoured.
COPY frontend/package.json frontend/pnpm-lock.yaml frontend/.npmrc ./
RUN pnpm install --frozen-lockfile

COPY frontend/ ./
# Same-origin API (served by the backend below), so no API base URL is baked in.
# The Supabase browser values are public (the publishable key is RLS-protected);
# defaults below match this project and can be overridden with --build-arg.
ARG VITE_SUPABASE_URL="https://ryuuuyeqewqwyzyytlbi.supabase.co"
ARG VITE_SUPABASE_ANON_KEY="sb_publishable_Ch6ssXDWyyg8WHod_q9fGw_IFOd6F2S"
ENV VITE_API_BASE_URL=""
ENV VITE_SUPABASE_URL=$VITE_SUPABASE_URL
ENV VITE_SUPABASE_ANON_KEY=$VITE_SUPABASE_ANON_KEY
RUN pnpm build

# ---------- stage 2: backend runtime ----------
FROM python:3.12-slim AS backend

# Model/cache downloads go to a world-writable dir (the container may run as a
# non-root user, so $HOME may not be writable).
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/tmp/hf \
    SENTENCE_TRANSFORMERS_HOME=/tmp/hf \
    TRANSFORMERS_CACHE=/tmp/hf

WORKDIR /app

# Install backend deps from pyproject (pulls torch + sentence-transformers).
COPY backend/pyproject.toml ./
COPY backend/app ./app
RUN pip install --no-cache-dir .

# Built SPA, served at the same origin as the API.
COPY --from=frontend /web/dist ./static

# Cloud Run provides $PORT (default 8080); bind to it, fall back for local runs.
EXPOSE 8080
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
