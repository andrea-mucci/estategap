"""Conversation and AI message models."""

from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from pydantic import Field

from ._base import AwareDatetime, EstateGapModel


class ChatMessage(EstateGapModel):
    id: int | None = None
    conversation_id: UUID | None = None
    role: Literal["user", "assistant", "system"]
    content: str
    criteria_snapshot: dict[str, Any] = Field(default_factory=dict)
    visual_refs: list[UUID] = Field(default_factory=list)
    tokens_used: int | None = None
    sent_at: AwareDatetime | None = None
    created_at: AwareDatetime | None = None


class ConversationState(EstateGapModel):
    id: UUID
    user_id: UUID | None = None
    language: str = "en"
    criteria_state: dict[str, Any] = Field(default_factory=dict)
    pending_dimensions: list[str] = Field(default_factory=list)
    alert_rule_id: UUID | None = None
    turn_count: int = 0
    status: Literal["active", "completed", "abandoned"] = "active"
    model_used: str | None = None
    messages: list[ChatMessage] = Field(default_factory=list)
    created_at: AwareDatetime
    updated_at: AwareDatetime


__all__ = ["ChatMessage", "ConversationState"]
