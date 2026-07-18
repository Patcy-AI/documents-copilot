# Document Copilot — Backend

FastAPI service. Managed with [`uv`](https://docs.astral.sh/uv/). See
[AGENTS.md](AGENTS.md) for conventions.

## Prerequisites

- Python 3.12+
- `uv` installed

## Setup

Run all commands from this `backend/` directory.

```bash
# 1. Install dependencies into backend/.venv
uv sync

# 2. Create your .env from the template and fill in the values
cp .env.example .env
```

`app/config.py` reads `.env` and fails fast on startup if a required variable
(Supabase keys, `DATABASE_URL`, `ANTHROPIC_API_KEY`) is missing.

## Run

```bash
uv run uvicorn app.main:app --reload
```

- API: http://localhost:8000
- Health check: http://localhost:8000/health
- Interactive docs: http://localhost:8000/docs

`--reload` restarts the server on code changes (dev only).

## Common commands

```bash
uv run pytest                     # run tests
uv run pytest -m "not integration"  # fast suite only (no network/DB)
uv run ruff check .               # lint
uv run ruff format .              # format
uv add <package>                  # add a dependency
uv add --dev <package>            # add a dev-only dependency
```

## Database migrations (Alembic)

```bash
uv run alembic upgrade head                        # apply migrations
uv run alembic revision --autogenerate -m "..."    # generate a candidate (review before applying)
```

Use the **direct** Supabase connection in `DATABASE_URL` (host
`db.<ref>.supabase.co`), not the transaction pooler — migrations need a session
connection.

## Note on virtual environments

`uv` manages `backend/.venv` (defined by `pyproject.toml`). If you see:

> `VIRTUAL_ENV=...\.venv does not match the project environment path .venv`

it's harmless — `uv` is ignoring an activated venv elsewhere and using
`backend/.venv` correctly. To silence it, `deactivate` any other venv first, or
pass `--active` to the `uv` command.

## Layout

```text
app/
├── main.py      # FastAPI entrypoint
├── config.py    # Pydantic settings — single source of truth for env
└── api/         # routers (added as built)
```
