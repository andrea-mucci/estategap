"""ChatMessage and ConversationState Pydantic models."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str
    sent_at: datetime
    listing_ids: list[str] = []


class ConversationState(BaseModel):
    id: str
    user_id: str
    messages: list[ChatMessage] = []
    created_at: datetime
    updated_at: datetime
