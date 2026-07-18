"""Database layer: SQLAlchemy models and metadata.

Import models from here so ``Base.metadata`` is fully populated for Alembic.
"""

from app.database.base import Base
from app.database.models import (
    ChatMessage,
    ChatThread,
    DocumentChunk,
    MessageCitation,
    SourceDocument,
    User,
)

__all__ = [
    "Base",
    "User",
    "SourceDocument",
    "DocumentChunk",
    "ChatThread",
    "ChatMessage",
    "MessageCitation",
]
