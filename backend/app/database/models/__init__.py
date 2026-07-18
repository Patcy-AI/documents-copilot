"""Model registry.

Importing this package imports every model module, so all classes are
registered on ``Base.metadata`` (required for Alembic autogenerate and for
SQLAlchemy to resolve cross-model relationships).
"""

from app.database.models.chat_message import ChatMessage
from app.database.models.chat_thread import ChatThread
from app.database.models.document_chunk import DocumentChunk
from app.database.models.message_citation import MessageCitation
from app.database.models.source_document import SourceDocument
from app.database.models.user import User

__all__ = [
    "User",
    "SourceDocument",
    "DocumentChunk",
    "ChatThread",
    "ChatMessage",
    "MessageCitation",
]
