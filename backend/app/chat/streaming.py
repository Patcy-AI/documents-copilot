"""Assistant streaming: retrieve -> ground -> stream answer + citations over SSE.

Wire format (SSE frames, separated by a blank line). Every frame carries a
single ``data:`` line holding a JSON value, plus an optional ``event:`` line:

* (no event) ``data: "<text fragment>"`` — an answer delta (a JSON string, so
  newlines inside the answer survive the SSE line framing).
* ``event: citations`` / ``data: [ ... ]`` — the source passages, sent once
  before the answer so the UI can render them alongside the reply.
* ``event: done`` / ``data: "end"`` — terminal frame.

The route accumulates the delta strings to persist the assistant message, and
reads the citations frame to persist ``message_citations``.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.chat.agent import stream_grounded_answer
from app.chat.retrieval import RetrievedChunk, retrieve

# Passage preview length surfaced to the UI and stored as the citation's quoted_text.
_EXCERPT_CHARS = 320

_REFUSAL = (
    "I couldn't find anything about that in the filings I have. This assistant "
    "only answers from 10-K annual reports for Apple, Amazon, Alphabet, "
    "Microsoft, and NVIDIA (fiscal years 2021-2025) - so if the question is "
    "about another company, period, or document, it's outside what I can see. "
    "I won't guess."
)


@dataclass
class Cited:
    """A citation to persist after the stream finishes."""

    chunk_id: str
    quoted_text: str
    score: float


def sse_event(data: str, event: str | None = None) -> str:
    """Format a single Server-Sent Event frame. ``data`` must be one line."""
    prefix = f"event: {event}\n" if event else ""
    return f"{prefix}data: {data}\n\n"


def _excerpt(text: str) -> str:
    text = text.strip()
    if len(text) > _EXCERPT_CHARS:
        return text[:_EXCERPT_CHARS].rstrip() + "…"
    return text


def _citation_frames(chunks: list[RetrievedChunk]) -> tuple[str, list[Cited]]:
    """Return the JSON payload for the UI and the rows to persist."""
    ui: list[dict] = []
    to_persist: list[Cited] = []
    for index, chunk in enumerate(chunks, start=1):
        excerpt = _excerpt(chunk.content)
        ui.append(
            {
                "n": index,
                "chunk_id": chunk.chunk_id,
                "filing": chunk.filing,
                "section": chunk.section,
                "excerpt": excerpt,
            }
        )
        to_persist.append(
            Cited(chunk_id=chunk.chunk_id, quoted_text=excerpt, score=chunk.score)
        )
    return json.dumps(ui), to_persist


async def generate_chat_events(
    db: AsyncSession, question: str
) -> AsyncIterator[tuple[str, str, object]]:
    """Yield ``(sse_frame, kind, payload)``; kind is ``delta``/``citations``/``done``.

    - ``delta``  payload is the text fragment (accumulate for persistence)
    - ``citations`` payload is ``list[Cited]`` (persist after the stream)
    - ``done``   payload is ``None``
    """
    result = await retrieve(db, question)

    if not result.has_relevant_context:
        for word in _REFUSAL.split(" "):
            delta = word + " "
            yield sse_event(json.dumps(delta)), "delta", delta
        yield sse_event(json.dumps("end"), event="done"), "done", None
        return

    payload_json, to_persist = _citation_frames(result.chunks)
    yield sse_event(payload_json, event="citations"), "citations", to_persist

    async for text in stream_grounded_answer(question, result.chunks):
        yield sse_event(json.dumps(text)), "delta", text

    yield sse_event(json.dumps("end"), event="done"), "done", None
