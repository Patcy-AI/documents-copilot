"""Chat thread and message persistence.

Ownership is enforced here in Python because the backend's direct Postgres
connection bypasses RLS (see ``app.database.session``). ``get_owned_thread`` is
the single choke point every read/write of a thread goes through.
"""

import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database.models import ChatMessage, ChatThread, MessageCitation


async def list_threads(db: AsyncSession, user_id: uuid.UUID) -> list[ChatThread]:
    """Threads owned by the user, most recently updated first."""
    result = await db.execute(
        select(ChatThread)
        .where(ChatThread.user_id == user_id)
        .order_by(ChatThread.updated_at.desc())
    )
    return list(result.scalars().all())


async def create_thread(
    db: AsyncSession, user_id: uuid.UUID, title: str | None = None
) -> ChatThread:
    thread = ChatThread(user_id=user_id, title=title)
    db.add(thread)
    await db.flush()  # populate server defaults (id, timestamps)
    return thread


async def get_owned_thread(
    db: AsyncSession, thread_id: uuid.UUID, user_id: uuid.UUID
) -> ChatThread:
    """Return the thread, or raise 404 if missing / 403 if owned by another user."""
    thread = await db.get(ChatThread, thread_id)
    if thread is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Thread not found"
        )
    if thread.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not your thread"
        )
    return thread


async def list_messages(
    db: AsyncSession, thread_id: uuid.UUID
) -> list[ChatMessage]:
    """Messages in a thread, oldest first. Caller must have checked ownership.

    Citations (and their chunks) are eager-loaded so the history view can show
    the same sources the analyst saw live, without an N+1 per message.
    """
    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.thread_id == thread_id)
        .order_by(ChatMessage.created_at)
        .options(
            selectinload(ChatMessage.citations).selectinload(MessageCitation.chunk)
        )
    )
    return list(result.scalars().all())


async def add_message(
    db: AsyncSession,
    thread_id: uuid.UUID,
    role: str,
    content: str,
    model: str | None = None,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
) -> ChatMessage:
    message = ChatMessage(
        thread_id=thread_id,
        role=role,
        content=content,
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )
    db.add(message)
    await db.flush()
    return message
