"""App-user persistence.

Supabase Auth owns ``auth.users``; the app's ``public.users`` row mirrors it and
is what chat threads / documents reference by foreign key. There is no DB trigger
copying signups across, so the backend upserts the current user on its first
write. Ownership of that row is trusted here: the id and email come from a token
already verified by ``app.auth.dependencies.get_current_user``.
"""

from sqlalchemy.dialects.postgresql import insert

from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import CurrentUser
from app.database.models import User


async def ensure_app_user(db: AsyncSession, user: CurrentUser) -> None:
    """Insert the app-side user row if missing; keep the email current."""
    statement = (
        insert(User)
        .values(id=user.id, email=user.email)
        .on_conflict_do_update(
            index_elements=[User.id],
            set_={"email": user.email},
        )
    )
    await db.execute(statement)
