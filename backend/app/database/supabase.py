"""Server-side Supabase client (service_role).

The backend connects with the ``service_role`` key, which **bypasses Row-Level
Security**. Never drive this client directly from untrusted input and never
expose the key to the browser — user scoping is enforced in the app layer
(see ``app.auth``), not by RLS on this connection.

Most schema and data access goes through SQLAlchemy (``app.database``); this
client is for what the Supabase SDK does best — Auth admin and Storage.

Follows the ``app.config.get_settings`` pattern: a cached singleton so the
client is constructed once per process.
"""

from functools import lru_cache

from supabase import Client, create_client

from app.config import settings


@lru_cache
def get_supabase() -> Client:
    """Return the process-wide service_role Supabase client (cached).

    Tests can call ``get_supabase.cache_clear()`` to force a rebuild.
    """
    return create_client(
        settings.supabase_url,
        settings.supabase_service_role_key,
    )
