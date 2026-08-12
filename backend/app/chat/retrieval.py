"""Hybrid retrieval over ``document_chunks``.

Embeds the analyst's question with the SAME local model used at ingest
(``BAAI/bge-small-en-v1.5``), then fuses two searches over ``document_chunks``:

* **semantic** — cosine distance on the pgvector ``embedding`` column (HNSW index),
* **keyword** — Postgres full-text over the generated ``content_tsv`` column.

Results are combined with Reciprocal Rank Fusion (RRF) so a chunk that ranks
well on *either* signal surfaces — exact figures/keywords aren't lost to pure
vector search, and paraphrases aren't lost to pure keyword search. The top
passages are returned with their filing/section metadata (for grounding +
citation) plus the best semantic similarity, so the caller can refuse when
nothing in the corpus is actually relevant.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache

from sentence_transformers import SentenceTransformer
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database.models import DocumentChunk

# bge-small retrieval asymmetry: passages were embedded plain at ingest; the
# QUERY gets this instruction prefix (per the model card + the ingest docstring).
_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "

# How many candidates each arm pulls, how many survive fusion, and the RRF const.
_CANDIDATES = 20
_TOP_K = 6
_RRF_K = 60

# Minimum cosine similarity (0..1) the best semantic hit must reach before we
# treat the question as answerable from the corpus. Below this we refuse rather
# than feed weak context to the model. The grounding prompt is the primary
# refusal mechanism; this is a secondary guard for truly-nothing queries.
MIN_SIMILARITY = 0.30


@lru_cache(maxsize=1)
def get_embedder() -> SentenceTransformer:
    """Process-wide embedding model, loaded once on first use."""
    return SentenceTransformer(settings.embedding_model)


def embed_query(question: str) -> list[float]:
    """Embed a query the way bge expects (instruction prefix + normalized)."""
    vector = get_embedder().encode(
        _QUERY_PREFIX + question,
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    return vector.tolist()


def filing_label(meta: dict) -> str:
    """Human filing label from chunk metadata, e.g. ``NVDA 10-K FY2025``."""
    year = meta.get("year")
    parts = [
        meta.get("ticker"),
        meta.get("form"),
        f"FY{year}" if year else None,
    ]
    label = " ".join(p for p in parts if p)
    return label or (meta.get("document_title") or "SEC filing")


def section_label(meta: dict) -> str | None:
    """Best in-filing locator for a citation.

    SEC 10-Ks are cited by Item/section, not page (EDGAR filings are HTML and
    have no pagination). Prefer the SEC Item heading (e.g. "Item 1A. Risk
    Factors"); fall back to the most specific heading, then the stored section.
    """
    headings = [
        h.strip()
        for h in (meta.get("headings") or [])
        if isinstance(h, str) and h.strip()
    ]
    for h in headings:
        if re.match(r"(?i)^item\s+\d+", h):
            return h
    if headings:
        return headings[-1]
    sec = meta.get("section")
    return sec.strip() if isinstance(sec, str) and sec.strip() else None


@dataclass
class RetrievedChunk:
    chunk_id: str
    content: str
    similarity: float  # best semantic similarity for this chunk (0..1)
    score: float  # fused RRF score
    metadata: dict

    @property
    def filing(self) -> str:
        return filing_label(self.metadata)

    @property
    def section(self) -> str | None:
        return section_label(self.metadata)


@dataclass
class Retrieval:
    chunks: list[RetrievedChunk]
    best_similarity: float

    @property
    def has_relevant_context(self) -> bool:
        return bool(self.chunks) and self.best_similarity >= MIN_SIMILARITY


async def retrieve(db: AsyncSession, question: str) -> Retrieval:
    """Return the top passages for a question, fused across semantic + keyword."""
    qvec = embed_query(question)

    # --- semantic arm: cosine distance, index-backed (HNSW, vector_cosine_ops) ---
    distance = DocumentChunk.embedding.cosine_distance(qvec).label("distance")
    sem_rows = (
        await db.execute(
            select(DocumentChunk, distance).order_by(distance).limit(_CANDIDATES)
        )
    ).all()

    # --- keyword arm: full-text rank over the generated tsvector ---
    tsquery = func.plainto_tsquery("english", question)
    rank = func.ts_rank_cd(DocumentChunk.content_tsv, tsquery).label("rank")
    kw_rows = (
        await db.execute(
            select(DocumentChunk, rank)
            .where(DocumentChunk.content_tsv.op("@@")(tsquery))
            .order_by(rank.desc())
            .limit(_CANDIDATES)
        )
    ).all()

    by_id: dict[str, DocumentChunk] = {}
    similarity: dict[str, float] = {}
    fused: dict[str, float] = {}

    # semantic: cosine distance -> similarity (normalized vectors: sim = 1 - dist)
    for position, (chunk, dist) in enumerate(sem_rows):
        cid = str(chunk.id)
        by_id[cid] = chunk
        similarity[cid] = 1.0 - float(dist)
        fused[cid] = fused.get(cid, 0.0) + 1.0 / (_RRF_K + position + 1)

    # keyword: RRF contribution by rank position
    for position, (chunk, _rank) in enumerate(kw_rows):
        cid = str(chunk.id)
        by_id.setdefault(cid, chunk)
        fused[cid] = fused.get(cid, 0.0) + 1.0 / (_RRF_K + position + 1)

    ordered = sorted(fused.items(), key=lambda kv: kv[1], reverse=True)[:_TOP_K]
    chunks = [
        RetrievedChunk(
            chunk_id=cid,
            content=by_id[cid].content,
            similarity=similarity.get(cid, 0.0),
            score=fscore,
            metadata=by_id[cid].metadata_ or {},
        )
        for cid, fscore in ordered
    ]

    best = max(similarity.values(), default=0.0)
    return Retrieval(chunks=chunks, best_similarity=best)
