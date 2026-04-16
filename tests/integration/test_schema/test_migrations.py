"""Migration round-trip validation."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Engine

from .conftest import LATEST_REVISION


def test_upgrade_head(db_engine: Engine, alembic_runner) -> None:
    alembic_runner("base", action="downgrade")
    alembic_runner("head", action="upgrade")

    with db_engine.connect() as connection:
        revision = connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()

    assert revision == LATEST_REVISION


def test_downgrade_base(db_engine: Engine, alembic_runner) -> None:
    alembic_runner("base", action="downgrade")

    with db_engine.connect() as connection:
        assert connection.execute(text("SELECT to_regclass('public.countries')")).scalar_one() is None
        assert connection.execute(text("SELECT to_regclass('public.listings')")).scalar_one() is None
        assert connection.execute(text("SELECT to_regclass('public.users')")).scalar_one() is None

    alembic_runner("head", action="upgrade")
