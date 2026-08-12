# Document Copilot — single-image deploy.
# Builds the React frontend, then serves it together with the FastAPI backend
# from one origin. Targets Hugging Face Spaces (Docker SDK, port 7860), which
# has enough RAM for the local embedding model + torch that free micro-tiers
# (e.g. 512 MB) can't fit.

# ---------- stage 1: build the frontend ----------
FROM node:22-slim AS frontend
WORKDIR /web

COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install

COPY frontend/ ./
# Same-origin API (served by the backend below), so no API base URL is baked in.
# The Supabase browser values are public (anon key is RLS-protected) and are
# passed as build args -> set them as HF Space "Variables".
ARG VITE_SUPABASE_URL
ARG VITE_SUPABASE_ANON_KEY
ENV VITE_API_BASE_URL=""
ENV VITE_SUPABASE_URL=$VITE_SUPABASE_URL
ENV VITE_SUPABASE_ANON_KEY=$VITE_SUPABASE_ANON_KEY
RUN npm run build

# ---------- stage 2: backend runtime ----------
FROM python:3.12-slim AS backend

# Model/cache downloads go to a world-writable dir (HF Spaces runs as a
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

EXPOSE 7860
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860"]
