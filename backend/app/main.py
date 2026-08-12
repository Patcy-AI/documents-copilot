"""FastAPI entrypoint for Document Copilot.

Run locally with:

    uv run uvicorn app.main:app --reload

Routers (chat, me) are registered under ``app.api``.
In the Docker deploy the built frontend is copied to ``static/`` and served
from this same app, so the whole product runs on one origin (no CORS).
"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.chat import router as chat_router
from app.api.me import router as me_router
from app.config import settings

# Populated by the Docker build (COPY frontend dist -> backend/static). Absent in
# local dev, where the SPA runs on the Vite dev server instead.
_STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

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


class _SpaStaticFiles(StaticFiles):
    """Serve the built SPA, falling back to index.html for client-side routes."""

    async def get_response(self, path: str, scope):
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            if exc.status_code == 404:
                return await super().get_response("index.html", scope)
            raise


# Mounted last so the API routes above always win. Only active when the built
# frontend is present (the Docker image), so local dev is unaffected.
if _STATIC_DIR.is_dir():
    app.mount(
        "/", _SpaStaticFiles(directory=str(_STATIC_DIR), html=True), name="spa"
    )
