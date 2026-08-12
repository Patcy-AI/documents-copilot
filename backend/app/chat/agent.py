"""Grounded answer generation with Claude.

Given the analyst's question and the retrieved passages, streams an answer that
is constrained to the corpus: it answers only from the supplied SOURCES, cites
them inline as ``[1]``/``[2]``, and refuses when the answer isn't present. This
is the product's trust guarantee — a wrong-but-confident answer is worse than
none, so outside knowledge is forbidden.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from anthropic import AsyncAnthropic

from app.chat.retrieval import RetrievedChunk
from app.config import settings

_CORPUS_SCOPE = (
    "10-K annual filings for Apple, Amazon, Alphabet, Microsoft, and NVIDIA, "
    "fiscal years 2021-2025"
)

_SYSTEM = (
    "You are Document Copilot, a research assistant for equity analysts. You "
    f"answer strictly from a fixed corpus of SEC filings: {_CORPUS_SCOPE}.\n\n"
    "Follow these rules exactly:\n"
    "1. Answer ONLY using the numbered SOURCES in the user message. Do not use "
    "any outside or prior knowledge, even if you know the answer.\n"
    "2. If the SOURCES do not contain the answer — or the question is about a "
    "company, filing, or period outside the corpus above — say so plainly "
    '(for example: "I don\'t have that in the current filings") and state what '
    "the corpus covers. Never guess, estimate, or fabricate a figure.\n"
    "3. Cite every factual claim inline with bracketed source numbers like [1] "
    "or [2], matching the SOURCES you actually used.\n"
    "4. Quote figures, dates, and names exactly as they appear in the SOURCES. "
    "Be concise and precise.\n"
    "5. Do not give investment advice, price targets, or buy/sell recommendations."
)


def _format_sources(chunks: list[RetrievedChunk]) -> str:
    blocks: list[str] = []
    for index, chunk in enumerate(chunks, start=1):
        header = chunk.filing
        if chunk.section:
            header += f" - {chunk.section}"
        blocks.append(f"[{index}] {header}\n{chunk.content.strip()}")
    return "\n\n".join(blocks)


async def stream_grounded_answer(
    question: str, chunks: list[RetrievedChunk]
) -> AsyncIterator[str]:
    """Yield answer text deltas from Claude, grounded on the given passages."""
    client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    user_content = (
        f"SOURCES:\n{_format_sources(chunks)}\n\n"
        f"QUESTION: {question}\n\n"
        "Answer using only the SOURCES above, with inline [n] citations. If the "
        "SOURCES do not answer the question, say you don't have it in the filings."
    )
    async with client.messages.stream(
        model=settings.anthropic_model,
        max_tokens=1024,
        system=_SYSTEM,
        messages=[{"role": "user", "content": user_content}],
    ) as stream:
        async for text in stream.text_stream:
            yield text
