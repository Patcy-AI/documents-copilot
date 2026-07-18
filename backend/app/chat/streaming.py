"""Stubbed assistant streaming.

Phase 3 has no LLM yet: we stream a canned reply word-by-word over SSE so the
whole chat UI + streaming + persistence path can be built and verified before
Claude and retrieval land. When the real agent arrives, only this generator
changes — the route, wire format, and frontend stay the same.

SSE framing: each delta is a ``data:`` line; a terminal ``event: done`` marks the
end. The caller accumulates deltas to persist the final assistant message.
"""

import asyncio
from collections.abc import AsyncIterator

_STUB_REPLY = (
    "This is a stubbed assistant reply. Retrieval and Claude are not wired up "
    "yet, so I can't answer from the filings — but the chat, streaming, and "
    "history are all working end to end."
)

# Small delay so the stream is visibly incremental in the UI.
_WORD_DELAY_SECONDS = 0.04


def sse_event(data: str, event: str | None = None) -> str:
    """Format a single Server-Sent Event frame."""
    prefix = f"event: {event}\n" if event else ""
    return f"{prefix}data: {data}\n\n"


async def stream_stub_reply() -> AsyncIterator[tuple[str, str]]:
    """Yield ``(sse_frame, delta_text)`` for each word, then a done frame.

    The delta text is yielded alongside the frame so the route can build the
    full reply for persistence without re-parsing the SSE stream.
    """
    words = _STUB_REPLY.split(" ")
    for index, word in enumerate(words):
        delta = word if index == 0 else f" {word}"
        yield sse_event(delta), delta
        await asyncio.sleep(_WORD_DELAY_SECONDS)
    yield sse_event("end", event="done"), ""
