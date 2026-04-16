"""Price history integration tests."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.engine import Engine

from .conftest import collect_plan_values


def test_append_price_changes(db_engine: Engine, listing_factory, price_history_factory) -> None:
    listing_id = listing_factory()
    now = datetime.now(timezone.utc)
    price_history_factory(listing_id=listing_id, old_price=260000, new_price=255000, recorded_at=now - timedelta(days=2))
    price_history_factory(listing_id=listing_id, old_price=255000, new_price=250000, recorded_at=now - timedelta(days=1))
    price_history_factory(listing_id=listing_id, old_price=250000, new_price=245000, recorded_at=now)

    with db_engine.connect() as connection:
        rows = connection.execute(
            text(
                """
                SELECT new_price
                FROM price_history
                WHERE listing_id = :listing_id
                ORDER BY recorded_at DESC
                """
            ),
            {"listing_id": listing_id},
        ).scalars().all()

    assert rows == [245000, 250000, 255000]


def test_price_history_index_usage(explain_json, listing_factory, price_history_factory) -> None:
    listing_id = listing_factory()
    price_history_factory(listing_id=listing_id)

    plan = explain_json(
        """
        SELECT id
        FROM price_history
        WHERE listing_id = :listing_id
        ORDER BY recorded_at DESC
        LIMIT 1
        """,
        {"listing_id": listing_id},
        disable_seqscan=True,
    )

    assert "price_history_listing_id_recorded_at_idx" in collect_plan_values(plan, "Index Name")


def test_no_fk_violation(db_engine: Engine, price_history_factory) -> None:
    orphan_listing_id = uuid4()
    price_history_factory(listing_id=orphan_listing_id, new_price=200000)

    with db_engine.connect() as connection:
        count = connection.execute(
            text("SELECT COUNT(*) FROM price_history WHERE listing_id = :listing_id"),
            {"listing_id": orphan_listing_id},
        ).scalar_one()

    assert count == 1
