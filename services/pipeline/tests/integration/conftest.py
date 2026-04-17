from __future__ import annotations

import os
from collections.abc import Callable, Iterator
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import asyncpg  # type: ignore[import-untyped]
import pytest
from alembic import command
from alembic.config import Config
from estategap_common.models import ListingStatus, NormalizedListing, PropertyCategory


testcontainers_postgres = pytest.importorskip("testcontainers.postgres")


REPO_ROOT = Path(__file__).resolve().parents[4]
PIPELINE_ROOT = REPO_ROOT / "services" / "pipeline"


@pytest.fixture(scope="session")
def database_url() -> Iterator[str]:
    container = testcontainers_postgres.PostgresContainer("postgis/postgis:16-3.4")
    try:
        container.start()
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"Docker is not available for PostgreSQL integration tests: {exc}")
    try:
        sqlalchemy_url = container.get_connection_url()
        _run_migrations(sqlalchemy_url)
        yield sqlalchemy_url.replace("+psycopg2", "")
    finally:
        container.stop()

@pytest.fixture
async def asyncpg_pool(database_url: str) -> Iterator[asyncpg.Pool]:
    pool = await asyncpg.create_pool(database_url, min_size=1, max_size=2, command_timeout=30)
    await _reset_database(pool)
    yield pool
    await _reset_database(pool)
    await pool.close()


@pytest.fixture
def normalized_listing_factory() -> Callable[..., NormalizedListing]:
    def _factory(**overrides: object) -> NormalizedListing:
        payload: dict[str, object] = {
            "id": uuid4(),
            "canonical_id": None,
            "country": "ES",
            "source": "idealista",
            "source_id": "listing-123",
            "source_url": "https://www.idealista.com/inmueble/listing-123/",
            "address": "Calle Mayor 1",
            "city": "Madrid",
            "region": "Madrid",
            "postal_code": "28013",
            "location_wkt": "POINT(-3.7038 40.4168)",
            "asking_price": Decimal("450000"),
            "currency": "EUR",
            "asking_price_eur": Decimal("450000"),
            "price_per_m2_eur": Decimal("5625"),
            "property_category": PropertyCategory.RESIDENTIAL,
            "property_type": "residential",
            "built_area_m2": Decimal("80"),
            "usable_area_m2": Decimal("75"),
            "plot_area_m2": Decimal("100"),
            "bedrooms": 3,
            "bathrooms": 2,
            "floor_number": 2,
            "total_floors": 4,
            "parking_spaces": 1,
            "has_lift": True,
            "has_pool": False,
            "year_built": 2005,
            "condition": "good",
            "energy_rating": "A",
            "status": ListingStatus.ACTIVE,
            "description_orig": "Sunny apartment in Madrid",
            "images_count": 12,
            "first_seen_at": datetime(2026, 4, 17, 12, 0, tzinfo=UTC),
            "last_seen_at": datetime(2026, 4, 17, 12, 0, tzinfo=UTC),
            "published_at": datetime(2026, 4, 17, 12, 0, tzinfo=UTC),
            "raw_hash": "a" * 64,
        }
        payload.update(overrides)
        return NormalizedListing.model_validate(payload)

    return _factory


def _run_migrations(sqlalchemy_url: str) -> None:
    alembic_cfg = Config(str(PIPELINE_ROOT / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(PIPELINE_ROOT / "alembic"))
    alembic_cfg.set_main_option("sqlalchemy.url", sqlalchemy_url)
    previous = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = sqlalchemy_url
    try:
        command.upgrade(alembic_cfg, "head")
    finally:
        if previous is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous


async def _reset_database(pool: asyncpg.Pool) -> None:
    async with pool.acquire() as conn:
        await conn.execute(
            """
            TRUNCATE TABLE quarantine, price_history, pois, listings RESTART IDENTITY CASCADE
            """
        )
        await conn.execute("DELETE FROM exchange_rates")
        await conn.executemany(
            """
            INSERT INTO exchange_rates (currency, date, rate_to_eur)
            VALUES ($1, $2, $3)
            """,
            [
                ("EUR", date(2026, 4, 17), Decimal("1")),
                ("GBP", date(2026, 4, 17), Decimal("1.17")),
                ("USD", date(2026, 4, 17), Decimal("0.91")),
            ],
        )
