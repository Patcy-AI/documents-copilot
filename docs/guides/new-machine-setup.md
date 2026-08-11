# New machine setup

How to bring Document Copilot up on a fresh laptop and resume where the last one
left off. The code lives on GitHub; the corpus and secrets do not, so most of the
work here is re-creating the parts git deliberately does not carry.

## Where the project stands

- All code is committed and pushed. The ingestion pipeline (`backend/ingest/`)
  is complete.
- The corpus is fully ingested: 25 `source_documents` embedded into 19,163
  `document_chunks` (384-dim vectors). This data already lives in Supabase, so a
  fresh machine does not need to re-run the ingest — just reconnect.
- Supabase is shared cloud state. The schema, users, and ingested corpus already
  live there — do **not** re-run migrations to recreate them; just connect.

## What does not come from `git clone`

| Thing | Why it's absent | How to restore |
| --- | --- | --- |
| `backend/.env`, `frontend/.env` | gitignored secrets (DB password, Anthropic key) | copy manually from the old machine |
| `data/downloads/` | large SEC HTML, gitignored | `uv run data/download.py` |
| `data/markdown/` (`.md` + `.json`) | derived, gitignored | `uv run data/convert/convert_to_markdown.py` |
| `document_chunks` rows | live in Supabase, not local | already ingested; re-run `uv run python -m ingest.chunk_and_embed` only to rebuild |

The `.env` files are the only piece with no reproduction script. Carry them over
by hand (password manager, encrypted drive) — never through git, Slack, or email.
`backend/.env.example` and `frontend/.env.example` document every key if you need
to regenerate them from the Supabase and Anthropic dashboards.

## Steps

Prerequisites: `git`, `uv` (Python >=3.12), Node.js.

```bash
# 1. Clone
git clone https://github.com/Patcy-AI/documents-copilot.git
cd documents-copilot

# 2. Install dependencies
cd backend && uv sync
cd ../frontend && pnpm install && cd ..

# 3. Put the two .env files in place (backend/ and frontend/) — see table above

# 4. Rebuild the local corpus (gitignored, reproducible)
uv run data/download.py                       # ~26 SEC filings
uv run data/convert/convert_to_markdown.py    # Docling -> .md + .json (~30-60 min)

# 5. (Optional) Rebuild embeddings — the corpus is already ingested in Supabase,
#    so only run this to regenerate chunks from scratch.
cd backend && uv run python -m ingest.chunk_and_embed
```

Step 5 downloads the bge model (~130 MB) to the HuggingFace cache on first run.
It commits per document, so an interrupted run resumes cleanly — with
`REPROCESS_ALL = False` (the default) it skips documents already marked `ready`.

Then launch the app per [backend-setup.md](backend-setup.md) and
[frontend-setup.md](frontend-setup.md).

## Verify the ingest worked

The corpus produces ~19,000 chunks across the 25 filings, each carrying a 384-dim
vector and — importantly — containing **no** `, 1 = . , 2 = .` table noise in
`content`. If you see that noise, the wrong table serializer is in use (see
below).

## Two deliberate choices in `chunk_and_embed.py` — do not "fix" them

Both look like they could be simplified. Both are defending against a specific
failure found by testing on real filings. They are recorded in the commit
message too, but they are easy to undo without noticing.

1. **Token budget is 510, not the model's 512.** `HuggingFaceTokenizer.count_tokens()`
   counts via `tokenize()`, which excludes the `[CLS]`/`[SEP]` special tokens the
   encoder adds at embed time. Budgeting to 512 let chunks land at a real 514 and
   silently lose their last two tokens. 510 leaves exact headroom.

2. **Tables serialize as Markdown, not Docling's default triplet format.**
   `ChunkingDocSerializer` defaults to `TripletTableSerializer`, which renders
   every cell as a coordinate/value pair. SEC filings use tables for page layout,
   not just financials, so that produced `, 1 = . , 2 = .` noise in ~74% of
   chunks. `MarkdownTableSerializer` (wired via `MarkdownTableProvider`) measured
   0%, with a lower max token count.

## Note: `docling` is a dev dependency

`chunk_and_embed.py` imports `docling_core` at runtime, but `docling` is declared
in the `dev` dependency group. `uv sync` installs dev groups by default, so local
runs work. A production install with `--no-dev` would fail on import — move it to
the main dependencies before deploying the ingest anywhere non-local.
