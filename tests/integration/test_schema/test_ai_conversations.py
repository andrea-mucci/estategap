"""AI conversation persistence tests."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Engine

from .conftest import collect_plan_values


def test_conversation_create(db_engine: Engine, user_factory, conversation_factory) -> None:
    user_id = user_factory()
    conversation_id = conversation_factory(user_id=user_id, language="es", turn_count=1)

    with db_engine.connect() as connection:
        row = connection.execute(
            text("SELECT user_id, language, turn_count FROM ai_conversations WHERE id = :conversation_id"),
            {"conversation_id": conversation_id},
        ).mappings().one()

    assert row["user_id"] == user_id
    assert row["language"] == "es"
    assert row["turn_count"] == 1


def test_message_append(db_engine: Engine, conversation_factory, message_factory) -> None:
    conversation_id = conversation_factory()
    message_factory(conversation_id=conversation_id, role="user", content="Need Lisbon listings")
    message_factory(conversation_id=conversation_id, role="assistant", content="Here are options")

    with db_engine.connect() as connection:
        count = connection.execute(
            text("SELECT COUNT(*) FROM ai_messages WHERE conversation_id = :conversation_id"),
            {"conversation_id": conversation_id},
        ).scalar_one()

    assert count == 2


def test_criteria_snapshot_roundtrip(db_engine: Engine, conversation_factory, message_factory) -> None:
    conversation_id = conversation_factory()
    snapshot = {"country": "ES", "max_price_eur": 200000}
    message_id = message_factory(conversation_id=conversation_id, criteria_snapshot=snapshot)

    with db_engine.connect() as connection:
        stored = connection.execute(
            text("SELECT criteria_snapshot FROM ai_messages WHERE id = :message_id"),
            {"message_id": message_id},
        ).scalar_one()

    assert stored == snapshot


def test_turn_count_index(explain_json, user_factory, conversation_factory) -> None:
    user_id = user_factory()
    conversation_factory(user_id=user_id, status="active")

    plan = explain_json(
        "SELECT id FROM ai_conversations WHERE user_id = :user_id AND status = 'active'",
        {"user_id": user_id},
        disable_seqscan=True,
    )

    assert "ai_conversations_user_id_status_idx" in collect_plan_values(plan, "Index Name")
