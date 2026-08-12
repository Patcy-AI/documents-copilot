"""Chat API — threads, history, and stubbed streaming.

Every route is authenticated via ``get_current_user``. Ownership is enforced
through ``get_owned_thread`` (the backend bypasses RLS on its direct
connection), so cross-user access returns 403.
"""

import uuid
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import CurrentUser, get_current_user
from app.chat.retrieval import filing_label
from app.chat.schemas import CitationOut, CreateThreadIn, MessageOut, StreamIn, ThreadOut
from app.chat.streaming import Cited, generate_chat_events
from app.config import settings
from app.database.chats import (
    add_message,
    create_thread,
    get_owned_thread,
    list_messages,
    list_threads,
)
from app.database.models import MessageCitation
from app.database.session import SessionLocal, get_db
from app.database.users import ensure_app_user

router = APIRouter(prefix="/chat", tags=["chat"])


@router.get("/threads", response_model=list[ThreadOut])
async def get_threads(
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ThreadOut]:
    threads = await list_threads(db, user.id)
    return [ThreadOut.model_validate(t) for t in threads]


@router.post("/threads", response_model=ThreadOut, status_code=201)
async def post_thread(
    body: CreateThreadIn,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ThreadOut:
    await ensure_app_user(db, user)
    thread = await create_thread(db, user.id, body.title)
    return ThreadOut.model_validate(thread)


@router.get("/threads/{thread_id}/messages", response_model=list[MessageOut])
async def get_messages(
    thread_id: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[MessageOut]:
    await get_owned_thread(db, thread_id, user.id)  # 404 / 403
    messages = await list_messages(db, thread_id)
    return [_message_out(m) for m in messages]


def _message_out(message) -> MessageOut:
    """Serialize a message plus its citations, labelling each cited filing."""
    citations = [
        CitationOut(
            chunk_id=c.chunk_id,
            filing=filing_label(c.chunk.metadata_ or {}),
            section=(c.chunk.metadata_ or {}).get("section"),
            excerpt=c.quoted_text,
        )
        for c in message.citations
    ]
    return MessageOut(
        id=message.id,
        role=message.role,
        content=message.content,
        created_at=message.created_at,
        citations=citations,
    )


@router.post("/stream")
async def chat_stream(
    body: StreamIn,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    # Ownership check before the 200 stream starts, so 403/404 are real statuses.
    await get_owned_thread(db, body.thread_id, user.id)

    async def event_stream() -> AsyncIterator[str]:
        # Own session: a Depends(get_db) session closes once streaming begins,
        # but we need to write the user message now and the assistant message
        # after the stream finishes.
        async with SessionLocal() as session:
            await add_message(session, body.thread_id, "user", body.message)
            await session.commit()

            parts: list[str] = []
            cited: list[Cited] = []
            async for frame, kind, payload in generate_chat_events(
                session, body.message
            ):
                if kind == "delta":
                    parts.append(payload)  # type: ignore[arg-type]
                elif kind == "citations":
                    cited = payload  # type: ignore[assignment]
                yield frame

            assistant = await add_message(
                session,
                body.thread_id,
                "assistant",
                "".join(parts),
                model=settings.anthropic_model,
            )
            for c in cited:
                session.add(
                    MessageCitation(
                        message_id=assistant.id,
                        chunk_id=uuid.UUID(c.chunk_id),
                        quoted_text=c.quoted_text,
                        score=c.score,
                    )
                )
            await session.commit()

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
