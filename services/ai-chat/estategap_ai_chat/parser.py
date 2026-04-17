"""Criteria-state extraction from streamed LLM output."""

from __future__ import annotations

from typing import Any, Literal
import json
import re

from pydantic import BaseModel, ConfigDict, Field, ValidationError


JSON_BLOCK_RE = re.compile(r"```json\s*(.*?)\s*```", re.IGNORECASE | re.DOTALL)


class ParseError(ValueError):
    """Raised when a JSON criteria block is malformed or invalid."""


class CriteriaState(BaseModel):
    """Validated criteria state emitted by the LLM."""

    model_config = ConfigDict(extra="forbid", strict=True)

    status: Literal["in_progress", "ready"]
    confidence: float = Field(ge=0.0, le=1.0)
    criteria: dict[str, Any]
    pending_dimensions: list[str]
    suggested_chips: list[str]
    show_visual_references: bool


def extract_criteria(text: str) -> CriteriaState | None:
    """Extract and validate the last fenced JSON criteria block from a response."""

    matches = JSON_BLOCK_RE.findall(text)
    if not matches:
        return None
    try:
        payload = json.loads(matches[-1])
    except json.JSONDecodeError as exc:
        raise ParseError("Malformed criteria JSON block") from exc
    try:
        return CriteriaState.model_validate(payload)
    except ValidationError as exc:
        raise ParseError("Criteria JSON failed validation") from exc
