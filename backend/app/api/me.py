"""Current-user route — the smallest authenticated endpoint.

Proves the full auth loop: the browser sends the Supabase bearer token, FastAPI
verifies it via ``get_current_user`` and returns the user. Every other protected
route reuses the same dependency.
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.auth.dependencies import CurrentUser, get_current_user

router = APIRouter(tags=["auth"])


class MeResponse(BaseModel):
    id: str
    email: str | None


@router.get("/me")
async def read_me(user: CurrentUser = Depends(get_current_user)) -> MeResponse:
    """Return the authenticated user derived from the verified bearer token."""
    return MeResponse(id=str(user.id), email=user.email)
