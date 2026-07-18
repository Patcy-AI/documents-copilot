"""FastAPI entrypoint for Document Copilot.

Run locally with:

    uv run uvicorn app.main:app --reload

Routers (chat, ingest, auth) are added under ``app.api`` as they're built.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.chat import router as chat_router
from app.api.me import router as me_router
from app.config import settings

app = FastAPI(title="Document Copilot")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(me_router)
app.include_router(chat_router)


@app.get("/health")
async def health() -> dict[str, str]:
    """Liveness probe — no external dependencies touched."""
    return {"status": "ok"}
