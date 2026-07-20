"""Chunk the corpus with Docling's HybridChunker, embed locally, fill ``document_chunks``.

For each ``source_documents`` row still ``pending``:
  1. load its ``DoclingDocument`` (the ``.json`` written by the converter),
  2. chunk it with ``HybridChunker`` — structure-aware, then token-aware,
  3. embed each chunk with the local model (BAAI/bge-small-en-v1.5 → 384 dims),
  4. insert ``document_chunks`` rows and flip the document to ``ready``.

Why HybridChunker (and why there is no regex cleaning left here):

* It chunks a ``DoclingDocument``, not Markdown. Markdown is a lossy export that
  flattens tables into pipe text; the JSON keeps real ``TableItem`` structure, so
  the repeated/empty-cell SEC noise never appears in the first place.
* ``HybridChunker`` IS the hierarchical chunker plus refinements — internally it
  runs a ``HierarchicalChunker`` (splitting on document structure), then splits
  anything over ``max_tokens`` and merges undersized neighbours that share the
  same headings (``merge_peers``). You do not run the two chunkers separately.

Length is enforced, not hoped for: the tokenizer handed to the chunker is the
SAME one the embedding model uses, so ``max_tokens`` is counted in the exact
units the encoder truncates on.

What gets embedded vs. stored:

* embed ``chunker.contextualize(chunk)`` — prepends the chunk's heading trail, so
  a bare table row embeds with the statement it came from rather than as loose
  numbers.
* store ``chunk.text`` (raw) in ``content`` — it is what Claude is shown and what
  citations point at, and ``content_tsv`` generates keyword search from it.

bge documents are embedded WITHOUT the query instruction prefix; the retrieval
step adds the "Represent this sentence..." prefix to queries only.

Run from ``backend/``:

    uv run python -m ingest.chunk_and_embed
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from docling_core.transforms.chunker.hierarchical_chunker import (
    ChunkingDocSerializer,
    ChunkingSerializerProvider,
)
from docling_core.transforms.chunker.hybrid_chunker import HybridChunker
from docling_core.transforms.chunker.tokenizer.huggingface import HuggingFaceTokenizer
from docling_core.transforms.serializer.markdown import MarkdownTableSerializer
from docling_core.types.doc.document import DoclingDocument
from sentence_transformers import SentenceTransformer
from sqlalchemy import delete, select

from app.config import settings
from app.database.models import DocumentChunk, SourceDocument
from app.database.session import SessionLocal

# Params: edit these, then run `uv run python -m ingest.chunk_and_embed`
MARKDOWN_DIR = Path(__file__).resolve().parents[2] / "data" / "markdown"
# bge-small-en-v1.5 caps at 512 tokens INCLUDING the [CLS]/[SEP] specials that
# sentence-transformers adds at encode time. The chunker's count_tokens() uses
# tokenize(), which excludes them — so budget 510 here to leave exact headroom,
# otherwise chunks that land on 512 silently lose their last two tokens.
MAX_TOKENS = 510
MERGE_PEERS = True           # merge undersized neighbours sharing the same headings
EMBED_BATCH = 64
REPROCESS_ALL = False        # True = re-chunk every doc (wipes its existing chunks)
LIMIT_DOCUMENTS = None       # e.g. 1 to spike a single filing before the full run


class MarkdownTableProvider(ChunkingSerializerProvider):
    """Serialize tables as Markdown rather than Docling's default triplet format.

    ``ChunkingDocSerializer`` defaults to ``TripletTableSerializer``, which renders
    every cell as a coordinate/value pair — on SEC filings (which use tables for
    page layout as well as financials) that produced ``, 1 = . , 2 = .`` noise in
    74% of chunks. Markdown tables measured 0%, with a lower max token count.
    """

    def get_serializer(self, doc: DoclingDocument) -> ChunkingDocSerializer:
        return ChunkingDocSerializer(doc=doc, table_serializer=MarkdownTableSerializer())


def build_chunker() -> HybridChunker:
    """HybridChunker bound to the embedding model's own tokenizer."""
    tokenizer = HuggingFaceTokenizer.from_pretrained(
        model_name=settings.embedding_model,
        max_tokens=MAX_TOKENS,
    )
    return HybridChunker(
        tokenizer=tokenizer,
        merge_peers=MERGE_PEERS,
        serializer_provider=MarkdownTableProvider(),
    )


def docling_json_path(source_uri: str) -> Path:
    """``2025/aapl_10-k_....md`` -> the sibling ``.json`` DoclingDocument."""
    return MARKDOWN_DIR / Path(source_uri).with_suffix(".json")


async def chunk_and_embed() -> None:
    print(f"Loading embedding model {settings.embedding_model} ...")
    model = SentenceTransformer(settings.embedding_model)
    dim = model.get_embedding_dimension()
    if dim != settings.embedding_dimensions:
        raise SystemExit(
            f"Model dim {dim} != settings.embedding_dimensions "
            f"{settings.embedding_dimensions}. Check EMBEDDING_MODEL."
        )

    chunker = build_chunker()
    total_chunks = 0
    over_limit = 0

    async with SessionLocal() as db:
        query = select(SourceDocument).order_by(SourceDocument.title)
        if not REPROCESS_ALL:
            query = query.where(SourceDocument.status != "ready")
        if LIMIT_DOCUMENTS:
            query = query.limit(LIMIT_DOCUMENTS)
        documents = (await db.execute(query)).scalars().all()

        if not documents:
            print("Nothing to do — all documents already 'ready'. "
                  "Set REPROCESS_ALL=True to rebuild.")
            return

        for doc in documents:
            json_path = docling_json_path(doc.source_uri)
            if not json_path.exists():
                print(f"  SKIP (no DoclingDocument): {doc.title} -> {json_path.name}")
                continue

            dl_doc = DoclingDocument.load_from_json(json_path)
            chunks = list(chunker.chunk(dl_doc))

            # Embed the contextualized form (headings + text); store the raw text.
            contextualized = [chunker.contextualize(c) for c in chunks]
            embeddings = model.encode(
                contextualized,
                batch_size=EMBED_BATCH,
                normalize_embeddings=True,
                show_progress_bar=False,
            )
            token_counts = [chunker.tokenizer.count_tokens(t) for t in contextualized]
            over_limit += sum(1 for t in token_counts if t > MAX_TOKENS)

            base_meta = doc.metadata_ or {}
            chunk_meta = {
                "ticker": base_meta.get("ticker"),
                "year": (base_meta.get("report_date") or "")[:4],
                "form": base_meta.get("form"),
                "accession_number": base_meta.get("accession_number"),
                "document_title": doc.title,
            }

            # Idempotent: clear any prior chunks for this doc, then insert fresh.
            await db.execute(
                delete(DocumentChunk).where(DocumentChunk.document_id == doc.id)
            )
            for index, (chunk, vector, tokens) in enumerate(
                zip(chunks, embeddings, token_counts, strict=True)
            ):
                headings = chunk.meta.headings or []
                db.add(
                    DocumentChunk(
                        document_id=doc.id,
                        chunk_index=index,
                        content=chunk.text,
                        token_count=tokens,
                        embedding=vector.tolist(),
                        metadata_={
                            **chunk_meta,
                            "section": headings[-1] if headings else None,
                            "headings": headings,
                        },
                    )
                )

            doc.status = "ready"
            await db.commit()  # per-doc: progress persists, run is resumable
            total_chunks += len(chunks)
            print(f"  {doc.title:18} -> {len(chunks):4} chunks")

    print(
        f"\nDone: {total_chunks} chunks embedded ({dim}-dim). "
        f"{over_limit} chunk(s) exceeded {MAX_TOKENS} tokens."
    )


if __name__ == "__main__":
    asyncio.run(chunk_and_embed())
