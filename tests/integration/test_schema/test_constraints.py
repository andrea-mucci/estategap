"""Constraint and generated-column validation for listings."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError


def test_unique_source_source_id(db_engine: Engine, listing_factory) -> None:
    listing_factory(country="ES", source="idealista", source_id="dup-123")
    with pytest.raises(IntegrityError):
        listing_factory(country="ES", source="idealista", source_id="dup-123")


def test_generated_days_on_market(db_engine: Engine, listing_factory) -> None:
    published_at = datetime.now(timezone.utc) - timedelta(days=10)
    listing_id = listing_factory(source_id="days-on-market", published_at=published_at)

    with db_engine.connect() as connection:
        days_on_market = connection.execute(
            text("SELECT days_on_market FROM listings WHERE id = :listing_id"),
            {"listing_id": listing_id},
        ).scalar_one()

    assert days_on_market >= 10
