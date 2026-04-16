"""Conversation and AI message models."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field

from ._base import EstateGapModel


class ChatMessage(EstateGapModel):
    id: int | None = None
    conversation_id: UUID | None = None
    role: Literal["user", "assistant", "system"]
    content: str
    criteria_snapshot: dict[str, object] = Field(default_factory=dict)
    visual_refs: list[UUID] = Field(default_factory=list)
    tokens_used: int | None = None
    sent_at: datetime | None = None
    created_at: datetime | None = None


class ConversationState(EstateGapModel):
    id: UUID
    user_id: UUID | None = None
    language: str = "en"
    criteria_state: dict[str, object] = Field(default_factory=dict)
    alert_rule_id: UUID | None = None
    turn_count: int = 0
    status: str = "active"
    model_used: str | None = None
    messages: list[ChatMessage] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
