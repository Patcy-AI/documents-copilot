"""Application configuration.

`app.config.settings` is the single source of truth for all environment-derived
configuration. Import `settings` wherever you need a value; never call
`os.getenv` or `load_dotenv` elsewhere in the app.

Required variables have no default, so a missing one raises a
``pydantic.ValidationError`` the first time this module is imported — the app
fails fast on startup instead of surfacing a confusing error deep in a request.
"""

from functools import lru_cache
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-backed settings.

    Field names map case-insensitively to the uppercase env vars documented in
    ``.env.example`` (e.g. ``supabase_url`` <- ``SUPABASE_URL``).
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Supabase (Auth + API) ---
    supabase_url: str
    supabase_anon_key: str
    supabase_service_role_key: str

    # --- Postgres (Alembic + direct DB access) ---
    # Direct/session connection (db.<ref>.supabase.co), not the transaction pooler.
    database_url: str

    # --- Anthropic / Claude (the LLM used for generation) ---
    # anthropic_model must be a valid public API model id (see the Anthropic
    # models docs). Override via ANTHROPIC_MODEL; e.g. claude-opus-5 for the
    # highest-quality answers, claude-haiku-4-5 for the cheapest.
    anthropic_api_key: str
    anthropic_model: str = "claude-sonnet-5"

    # --- Embeddings (local, free — sentence-transformers, no API key) ---
    # EMBEDDING_DIMENSIONS must match the pgvector column width in Supabase.
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    embedding_dimensions: int = 384

    # --- Server ---
    # Comma-separated browser origins allowed to call the API (CORS).
    # NoDecode disables pydantic-settings' JSON pre-parse so the validator below
    # handles the plain `a,b,c` form.
    allowed_origins: Annotated[list[str], NoDecode] = ["http://localhost:5173"]

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def _split_comma_separated(cls, value: object) -> object:
        """Parse ALLOWED_ORIGINS as a comma-separated string.

        pydantic-settings would otherwise try to JSON-decode a list-typed env
        var, which breaks on plain ``a,b,c`` input.
        """
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings singleton.

    Cached so the ``.env`` file and environment are read once. Tests can call
    ``get_settings.cache_clear()`` to force a reload.
    """
    return Settings()


settings = get_settings()
