"""initial schema

Creates the full Document Copilot schema: users, source_documents,
document_chunks (with a vector(384) embedding + generated tsvector), chat_threads,
chat_messages, message_citations — plus the pgvector extension, HNSW/GIN indexes,
the auth.users foreign key, and owner-scoped RLS policies.

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-07-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0001_initial_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # pgvector must exist before any vector column is created.
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # --- users (mirrors auth.users) ---
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.Text(), nullable=True),
        sa.Column("full_name", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
        sa.ForeignKeyConstraint(
            ["id"], ["auth.users.id"], name="fk_users_id_auth_users", ondelete="CASCADE"
        ),
    )

    # --- source_documents ---
    op.create_table(
        "source_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("source_type", sa.Text(), nullable=False),
        sa.Column("source_uri", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), server_default=sa.text("'pending'"), nullable=False),
        sa.Column("metadata", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_source_documents"),
        sa.ForeignKeyConstraint(
            ["owner_id"], ["users.id"], name="fk_source_documents_owner_id_users", ondelete="CASCADE"
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'processing', 'ready', 'failed')",
            name="status_valid",
        ),
    )
    op.create_index("ix_source_documents_owner_id", "source_documents", ["owner_id"])

    # --- document_chunks (embedding + generated full-text vector) ---
    op.create_table(
        "document_chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=True),
        sa.Column("embedding", Vector(384), nullable=True),
        sa.Column(
            "content_tsv",
            postgresql.TSVECTOR(),
            sa.Computed("to_tsvector('english', content)", persisted=True),
            nullable=False,
        ),
        sa.Column("metadata", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_document_chunks"),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["source_documents.id"],
            name="fk_document_chunks_document_id_source_documents",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("document_id", "chunk_index", name="document_chunk"),
    )
    op.create_index("ix_document_chunks_document_id", "document_chunks", ["document_id"])
    # Keyword retrieval over the generated tsvector.
    op.create_index(
        "ix_document_chunks_content_tsv", "document_chunks", ["content_tsv"], postgresql_using="gin"
    )
    # Approximate-nearest-neighbour search over embeddings (cosine distance).
    op.create_index(
        "ix_document_chunks_embedding",
        "document_chunks",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
        postgresql_with={"m": 16, "ef_construction": 64},
    )

    # --- chat_threads ---
    op.create_table(
        "chat_threads",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_chat_threads"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_chat_threads_user_id_users", ondelete="CASCADE"
        ),
    )
    op.create_index("ix_chat_threads_user_id", "chat_threads", ["user_id"])

    # --- chat_messages (assistant turns generated by Claude) ---
    op.create_table(
        "chat_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("thread_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("model", sa.Text(), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_chat_messages"),
        sa.ForeignKeyConstraint(
            ["thread_id"],
            ["chat_threads.id"],
            name="fk_chat_messages_thread_id_chat_threads",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint("role IN ('user', 'assistant', 'system')", name="role_valid"),
    )
    op.create_index("ix_chat_messages_thread_id", "chat_messages", ["thread_id"])

    # --- message_citations ---
    op.create_table(
        "message_citations",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("message_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chunk_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("quoted_text", sa.Text(), nullable=True),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_message_citations"),
        sa.ForeignKeyConstraint(
            ["message_id"],
            ["chat_messages.id"],
            name="fk_message_citations_message_id_chat_messages",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["chunk_id"],
            ["document_chunks.id"],
            name="fk_message_citations_chunk_id_document_chunks",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("message_id", "chunk_id", name="message_chunk"),
    )
    op.create_index("ix_message_citations_message_id", "message_citations", ["message_id"])
    op.create_index("ix_message_citations_chunk_id", "message_citations", ["chunk_id"])

    # --- Row Level Security ---
    # The backend connects as the table owner (postgres) via DATABASE_URL and
    # bypasses RLS. These policies scope direct client access (Supabase
    # anon/authenticated roles) to the signed-in user's own rows via auth.uid().
    op.execute("ALTER TABLE users ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY users_owner ON users "
        "FOR ALL USING (auth.uid() = id) WITH CHECK (auth.uid() = id)"
    )

    op.execute("ALTER TABLE source_documents ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY source_documents_owner ON source_documents "
        "FOR ALL USING (auth.uid() = owner_id) WITH CHECK (auth.uid() = owner_id)"
    )

    op.execute("ALTER TABLE document_chunks ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY document_chunks_owner ON document_chunks FOR ALL "
        "USING (EXISTS (SELECT 1 FROM source_documents d "
        "WHERE d.id = document_chunks.document_id AND d.owner_id = auth.uid())) "
        "WITH CHECK (EXISTS (SELECT 1 FROM source_documents d "
        "WHERE d.id = document_chunks.document_id AND d.owner_id = auth.uid()))"
    )

    op.execute("ALTER TABLE chat_threads ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY chat_threads_owner ON chat_threads "
        "FOR ALL USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id)"
    )

    op.execute("ALTER TABLE chat_messages ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY chat_messages_owner ON chat_messages FOR ALL "
        "USING (EXISTS (SELECT 1 FROM chat_threads t "
        "WHERE t.id = chat_messages.thread_id AND t.user_id = auth.uid())) "
        "WITH CHECK (EXISTS (SELECT 1 FROM chat_threads t "
        "WHERE t.id = chat_messages.thread_id AND t.user_id = auth.uid()))"
    )

    op.execute("ALTER TABLE message_citations ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY message_citations_owner ON message_citations FOR ALL "
        "USING (EXISTS (SELECT 1 FROM chat_messages m "
        "JOIN chat_threads t ON t.id = m.thread_id "
        "WHERE m.id = message_citations.message_id AND t.user_id = auth.uid())) "
        "WITH CHECK (EXISTS (SELECT 1 FROM chat_messages m "
        "JOIN chat_threads t ON t.id = m.thread_id "
        "WHERE m.id = message_citations.message_id AND t.user_id = auth.uid()))"
    )


def downgrade() -> None:
    # Dropping a table drops its indexes, RLS policies, and RLS state with it.
    op.drop_table("message_citations")
    op.drop_table("chat_messages")
    op.drop_table("chat_threads")
    op.drop_table("document_chunks")
    op.drop_table("source_documents")
    op.drop_table("users")
    # The `vector` extension is left in place (other objects may depend on it).
