"""Wire models for the chat API.

Response models use ``from_attributes`` so they serialize ORM rows directly.
``StreamIn`` is our own simple request shape (not the Vercel AI SDK message
format) — the browser sends one new user message plus its thread id.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ThreadOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str | None
    created_at: datetime
    updated_at: datetime


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    role: str
    content: str
    created_at: datetime


class CreateThreadIn(BaseModel):
    title: str | None = None


class StreamIn(BaseModel):
    thread_id: uuid.UUID
    message: str
