"""Supabase JWT verification and the current-user dependency.

The frontend sends the user's Supabase access token as
``Authorization: Bearer <token>``. We verify it by calling Supabase Auth's user
endpoint over HTTP — simpler and safer than local JWT validation for the first
implementation (see ``docs/architecture.md``). If request volume grows, local
JWT signature verification can slot in behind this same dependency without
changing any callers.

The call is made with async ``httpx`` so it never blocks the event loop.
"""

import uuid
from dataclasses import dataclass

import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import settings

# auto_error=False so we return a clean 401 (not FastAPI's default 403) when the
# Authorization header is missing.
_bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class CurrentUser:
    """The authenticated Supabase user, derived from a verified token."""

    id: uuid.UUID
    email: str | None


async def _fetch_supabase_user(token: str) -> dict | None:
    """Return the Supabase user for a token, or ``None`` if it's invalid."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(
            f"{settings.supabase_url}/auth/v1/user",
            headers={
                "Authorization": f"Bearer {token}",
                "apikey": settings.supabase_anon_key,
            },
        )
    if response.status_code != 200:
        return None
    return response.json()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> CurrentUser:
    """FastAPI dependency: verify the bearer token and return the current user.

    Raises ``401`` if the header is missing or the token is invalid/expired.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
        )

    user = await _fetch_supabase_user(credentials.credentials)
    try:
        user_id = uuid.UUID(user["id"]) if user else None
    except (ValueError, TypeError, KeyError):
        user_id = None
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    return CurrentUser(id=user_id, email=user.get("email"))
