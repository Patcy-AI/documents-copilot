"""User model — the app user, mirroring a Supabase auth.users row."""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.database.models.chat_thread import ChatThread
    from app.database.models.source_document import SourceDocument


class User(TimestampMixin, Base):
    __tablename__ = "users"

    # id mirrors auth.users.id. The REFERENCES auth.users(id) FK and the RLS
    # policies are added in the migration — the auth schema is Supabase-managed
    # and must not be part of this app's SQLAlchemy metadata.
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    email: Mapped[str | None] = mapped_column(Text)
    full_name: Mapped[str | None] = mapped_column(Text)

    documents: Mapped[list["SourceDocument"]] = relationship(
        back_populates="owner", cascade="all, delete-orphan"
    )
    threads: Mapped[list["ChatThread"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
