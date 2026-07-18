"""Alembic migration environment.

The database URL and target metadata come from the application, not from
``alembic.ini`` — so there are no secrets in the ini file and the schema stays
in sync with the SQLAlchemy models.
"""

from logging.config import fileConfig

from sqlalchemy import create_engine, pool

from alembic import context

from app.config import settings
from app.database import Base  # noqa: F401 — imports every model, populating Base.metadata

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def _database_url() -> str:
    """DATABASE_URL forced onto the psycopg (v3) driver we depend on.

    Use the direct/session Supabase connection (db.<ref>.supabase.co), never the
    transaction pooler — migrations need a session connection.
    """
    url = settings.database_url
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


target_metadata = Base.metadata


def include_object(obj, name, type_, reflected, compare_to) -> bool:
    """Keep Supabase-managed objects out of autogenerate diffs.

    The ``users.id -> auth.users.id`` FK lives only in the migration (the auth
    schema is not part of our metadata), so without this hook every autogenerate
    run would try to drop it.
    """
    if type_ == "foreign_key_constraint":
        referred = getattr(obj, "referred_table", None)
        if referred is not None and referred.schema == "auth":
            return False
    return True


def run_migrations_offline() -> None:
    """Emit SQL without a live connection (``alembic ... --sql``)."""
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        include_object=include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against a live database connection."""
    # Build the engine directly from the app URL — this keeps the (possibly
    # %-containing) password out of ConfigParser, which would misread it as
    # interpolation syntax.
    connectable = create_engine(_database_url(), poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            include_object=include_object,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
