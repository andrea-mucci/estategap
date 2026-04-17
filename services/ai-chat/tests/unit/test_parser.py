from __future__ import annotations

import pytest

from estategap_ai_chat.parser import ParseError, extract_criteria


def test_extract_criteria_returns_state_for_valid_json_block() -> None:
    state = extract_criteria(
        "Let me refine that.\n```json\n"
        '{"status":"in_progress","confidence":0.5,"criteria":{"location":"milan"},'
        '"pending_dimensions":["price_range"],"suggested_chips":["2 bedrooms"],'
        '"show_visual_references":false}\n```'
    )

    assert state is not None
    assert state.criteria["location"] == "milan"


def test_extract_criteria_raises_for_malformed_json() -> None:
    with pytest.raises(ParseError):
        extract_criteria("```json\n{\"status\": \"in_progress\",}\n```")


def test_extract_criteria_returns_none_when_missing_json_block() -> None:
    assert extract_criteria("No structured output here.") is None


def test_extract_criteria_raises_when_validation_fails() -> None:
    with pytest.raises(ParseError):
        extract_criteria("```json\n{\"status\":\"bogus\"}\n```")


def test_extract_criteria_uses_last_json_block() -> None:
    state = extract_criteria(
        "```json\n"
        '{"status":"in_progress","confidence":0.1,"criteria":{},'
        '"pending_dimensions":["location"],"suggested_chips":[],'
        '"show_visual_references":false}\n```\n'
        "Later block.\n"
        "```json\n"
        '{"status":"ready","confidence":0.9,"criteria":{"location":"turin"},'
        '"pending_dimensions":[],"suggested_chips":["search now"],'
        '"show_visual_references":true}\n```'
    )

    assert state is not None
    assert state.status == "ready"
    assert state.criteria["location"] == "turin"
