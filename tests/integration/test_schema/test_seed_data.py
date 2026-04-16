"""Seed-data checks for migration 010."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Engine


def test_countries_seeded(db_engine: Engine) -> None:
    with db_engine.connect() as connection:
        count = connection.execute(
            text("SELECT COUNT(*) FROM countries WHERE code IN ('ES', 'IT', 'PT', 'FR', 'GB')"),
        ).scalar_one()

    assert count == 5


def test_portals_seeded(db_engine: Engine) -> None:
    with db_engine.connect() as connection:
        count = connection.execute(text("SELECT COUNT(*) FROM portals")).scalar_one()

    assert count == 10


def test_portal_spider_classes(db_engine: Engine) -> None:
    with db_engine.connect() as connection:
        count = connection.execute(
            text("SELECT COUNT(*) FROM portals WHERE spider_class IS NOT NULL AND spider_class <> ''"),
        ).scalar_one()

    assert count == 10


def test_seed_downgrade(db_engine: Engine, alembic_runner) -> None:
    alembic_runner("-1", action="downgrade")

    with db_engine.connect() as connection:
        countries = connection.execute(text("SELECT COUNT(*) FROM countries")).scalar_one()
        portals = connection.execute(text("SELECT COUNT(*) FROM portals")).scalar_one()

    assert countries == 0
    assert portals == 0

    alembic_runner("head", action="upgrade")
