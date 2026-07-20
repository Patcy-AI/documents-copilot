"""Load the converted Markdown corpus into the ``source_documents`` table.

Reads ``data/markdown/manifest.json`` (produced by
``data/convert/convert_to_markdown.py``) and inserts one catalog row per filing.

Design note: this project's ``source_documents`` is a lightweight **catalog** —
title, type, a ``source_uri`` pointer to the ``.md`` file, and rich ``metadata``.
The actual text is NOT stored here; it flows into ``document_chunks`` in the next
step (chunking + embedding), which reads the Markdown from ``source_uri``. No
schema migration is needed.

Run from ``backend/``:

    uv run python -m ingest.load_source_documents

Config flags below: SKIP_EXISTING skips filings already loaded (matched by
``source_uri``) so re-runs are idempotent; set it False to refresh those rows.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from sqlalchemy import select

from app.database.models import SourceDocument, User
from app.database.session import SessionLocal

# Params: edit these, then run `uv run python -m ingest.load_source_documents`
# The corpus is Driftwood-internal and shared; retrieval is not owner-scoped, so
# owner_id is nominal here — we attribute the catalog rows to one existing user.
OWNER_EMAIL = "patmaikasuwa@gmail.com"
SKIP_EXISTING = True

MARKDOWN_DIR = Path(__file__).resolve().parents[2] / "data" / "markdown"


def _title(filing: dict) -> str:
    """e.g. 'AAPL 10-K 2025' from ticker/form/report year."""
    year = (filing.get("report_date") or filing.get("filing_date") or "")[:4]
    return f"{filing['ticker']} {filing['form']} {year}".strip()


def _metadata(filing: dict) -> dict:
    """Carry the useful filing fields into the JSONB column for later filtering."""
    return {
        "ticker": filing["ticker"],
        "cik": filing["cik"],
        "form": filing["form"],
        "filing_date": filing["filing_date"],
        "report_date": filing["report_date"],
        "accession_number": filing["accession_number"],
        "source_url": filing["source_url"],
        "markdown_path": filing["local_path"],
        "source_html_path": filing.get("source_html_path"),
    }


async def load_source_documents() -> None:
    manifest_path = MARKDOWN_DIR / "manifest.json"
    if not manifest_path.exists():
        raise SystemExit(
            f"No manifest at {manifest_path}. "
            "Run data/convert/convert_to_markdown.py first."
        )

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    filings = manifest.get("filings", [])

    async with SessionLocal() as db:
        owner = (
            await db.execute(select(User).where(User.email == OWNER_EMAIL))
        ).scalar_one_or_none()
        if owner is None:
            raise SystemExit(
                f"No user with email {OWNER_EMAIL} in public.users. "
                "Sign in through the app once so the user row exists, or set "
                "OWNER_EMAIL to an existing user."
            )

        inserted = updated = skipped = 0
        for filing in filings:
            source_uri = filing["local_path"]  # e.g. 2025/aapl_10-k_....md
            existing = (
                await db.execute(
                    select(SourceDocument).where(
                        SourceDocument.owner_id == owner.id,
                        SourceDocument.source_uri == source_uri,
                    )
                )
            ).scalar_one_or_none()

            if existing is not None:
                if SKIP_EXISTING:
                    skipped += 1
                    continue
                existing.title = _title(filing)
                existing.source_type = "markdown"
                existing.status = "pending"
                existing.metadata_ = _metadata(filing)
                updated += 1
                continue

            db.add(
                SourceDocument(
                    owner_id=owner.id,
                    title=_title(filing),
                    source_type="markdown",
                    source_uri=source_uri,
                    status="pending",  # awaiting chunking + embedding
                    metadata_=_metadata(filing),
                )
            )
            inserted += 1

        await db.commit()

    print(
        f"source_documents: {inserted} inserted, {updated} updated, "
        f"{skipped} skipped (of {len(filings)} filings)."
    )


if __name__ == "__main__":
    asyncio.run(load_source_documents())
