# /// script
# requires-python = ">=3.12"
# dependencies = ["docling==2.112.0"]
# ///
"""Convert downloaded SEC HTML filings to Markdown + DoclingDocument JSON.

Reads ``data/downloads/manifest.json``, converts each HTML filing, and mirrors
the same year-folder structure under ``data/markdown/`` plus a parallel
``manifest.json`` — so the corpus is ready for chunking/embedding.

Two artifacts are written per filing:

* ``.md``   — human-readable export, handy for eyeballing the corpus.
* ``.json`` — the full ``DoclingDocument``. This is the one that matters:
  ``HybridChunker.chunk()`` takes a ``DoclingDocument``, NOT Markdown, and the
  JSON preserves real ``TableItem`` structure. Markdown flattens tables to pipe
  text, which is where the repeated/empty-cell SEC noise comes from — chunking
  from JSON avoids it instead of regex-cleaning it afterwards.

Standalone (not part of the backend package): run with

    uv run data/convert/convert_to_markdown.py

Docling is declared inline (PEP 723), so ``uv`` builds an isolated env for it.
"""

from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

from docling.document_converter import DocumentConverter

# Params: edit these, then run `uv run data/convert/convert_to_markdown.py`
DOCLING_VERSION = "2.112.0"
DATA_DIR = Path(__file__).resolve().parent.parent
DOWNLOADS_DIR = DATA_DIR / "downloads"
MARKDOWN_DIR = DATA_DIR / "markdown"
CLEAR_OUTPUT_DIR = True


def _normalize(local_path: str) -> PurePosixPath:
    """Manifest paths may use Windows separators; normalize to a posix path."""
    return PurePosixPath(local_path.replace("\\", "/"))


def convert_filings() -> dict:
    source_manifest_path = DOWNLOADS_DIR / "manifest.json"
    if not source_manifest_path.exists():
        raise SystemExit(
            f"No manifest at {source_manifest_path}. Run data/download.py first."
        )

    source_manifest = json.loads(source_manifest_path.read_text(encoding="utf-8"))

    if CLEAR_OUTPUT_DIR and MARKDOWN_DIR.exists():
        shutil.rmtree(MARKDOWN_DIR)
    MARKDOWN_DIR.mkdir(parents=True, exist_ok=True)

    # One converter, reused across files so models load once.
    converter = DocumentConverter()

    out_filings: list[dict] = []
    failures: list[dict] = []

    for filing in source_manifest.get("filings", []):
        rel = _normalize(filing["local_path"])
        html_path = DOWNLOADS_DIR / rel
        md_rel = rel.with_suffix(".md")
        md_path = MARKDOWN_DIR / md_rel
        json_rel = rel.with_suffix(".json")
        json_path = MARKDOWN_DIR / json_rel

        label = f"{filing.get('ticker', '?')} {rel}"
        if not html_path.exists():
            print(f"  SKIP (missing HTML): {label}")
            failures.append({"local_path": str(rel), "error": "source HTML missing"})
            continue

        print(f"Converting {label} ...")
        try:
            result = converter.convert(html_path)
            markdown = result.document.export_to_markdown()
        except Exception as exc:  # keep going; one bad filing shouldn't stop the run
            print(f"  ERROR: {exc}")
            failures.append({"local_path": str(rel), "error": str(exc)})
            continue

        md_path.parent.mkdir(parents=True, exist_ok=True)
        md_path.write_text(markdown, encoding="utf-8")
        result.document.save_as_json(json_path)  # the chunker's actual input

        entry = dict(filing)  # carry ticker/cik/dates/accession forward
        entry["source_html_path"] = str(rel)
        entry["local_path"] = str(md_rel)  # now points at the Markdown file
        entry["docling_json_path"] = str(json_rel)
        out_filings.append(entry)

    manifest = {
        "source": "SEC EDGAR (HTML converted to Markdown)",
        "converter": f"docling=={DOCLING_VERSION}",
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "form": source_manifest.get("form"),
        "converted_count": len(out_filings),
        "failed_count": len(failures),
        "filings": out_filings,
        "failures": failures,
    }
    manifest_path = MARKDOWN_DIR / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


if __name__ == "__main__":
    result = convert_filings()
    print(
        f"\nConverted {result['converted_count']} filing(s) to {MARKDOWN_DIR}"
        f" ({result['failed_count']} failed)."
    )
    print(f"Manifest: {MARKDOWN_DIR / 'manifest.json'}")
