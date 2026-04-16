"""Integration fixtures for schema validation against PostgreSQL + PostGIS."""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.engine import Engine
from testcontainers.postgres import PostgresContainer

LATEST_REVISION = "d4e5f6a1b2c4"
DYNAMIC_TABLES = [
    "alert_log",
    "ai_messages",
    "ai_conversations",
    "alert_rules",
    "ml_model_versions",
    "price_history",
    "listings",
    "zones",
    "users",
]


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _pipeline_dir() -> Path:
    return _repo_root() / "services" / "pipeline"


def make_alembic_config(database_url: str) -> Config:
    """Create an Alembic configuration for the pipeline migrations."""

    pipeline_dir = _pipeline_dir()
    config = Config(str(pipeline_dir / "alembic.ini"))
    config.set_main_option("script_location", str(pipeline_dir / "alembic"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def run_alembic(database_url: str, revision: str, action: str = "upgrade") -> None:
    """Run an Alembic upgrade or downgrade for the pipeline service."""

    config = make_alembic_config(database_url)
    if action == "upgrade":
        command.upgrade(config, revision)
    else:
        command.downgrade(config, revision)


def parse_plan(plan_payload: Any) -> dict[str, Any]:
    """Normalize the first JSON EXPLAIN plan row into a dictionary."""

    if isinstance(plan_payload, str):
        parsed = json.loads(plan_payload)
    else:
        parsed = plan_payload
    if isinstance(parsed, list):
        return parsed[0]
    return parsed


def collect_plan_values(plan: Any, key: str) -> set[str]:
    """Collect every value for a given key inside a JSON query plan."""

    values: set[str] = set()
    if isinstance(plan, dict):
        if key in plan and isinstance(plan[key], str):
            values.add(plan[key])
        for value in plan.values():
            values.update(collect_plan_values(value, key))
    elif isinstance(plan, list):
        for item in plan:
            values.update(collect_plan_values(item, key))
    return values


@pytest.fixture(scope="session")
def database_url() -> Iterator[str]:
    """Start a PostGIS container and expose its SQLAlchemy URL."""

    with PostgresContainer(
        "postgis/postgis:16-3.4",
        username="estategap",
        password="estategap",
        dbname="estategap",
    ) as container:
        url = container.get_connection_url()
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+psycopg2://", 1)
        yield url


@pytest.fixture(scope="session")
def db_engine(database_url: str) -> Iterator[Engine]:
    """Create an engine with the schema migrated to head."""

    run_alembic(database_url, "head")
    engine = sa.create_engine(database_url, future=True)
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def alembic_runner(database_url: str) -> Callable[[str, str], None]:
    """Expose an Alembic runner for migration round-trip tests."""

    def _runner(revision: str, action: str = "upgrade") -> None:
        run_alembic(database_url, revision, action)

    return _runner


@pytest.fixture(autouse=True)
def cleanup_dynamic_tables(db_engine: Engine) -> Iterator[None]:
    """Keep test cases isolated while preserving seeded reference data."""

    yield
    with db_engine.begin() as connection:
        users_exists = connection.execute(
            text("SELECT to_regclass('public.users') IS NOT NULL")
        ).scalar_one()
        if not users_exists:
            return
        connection.execute(
            text(
                "TRUNCATE TABLE "
                + ", ".join(DYNAMIC_TABLES)
                + " RESTART IDENTITY CASCADE"
            )
        )
        refresh_fn_exists = connection.execute(
            text("SELECT to_regprocedure('refresh_zone_statistics()') IS NOT NULL")
        ).scalar_one()
        if refresh_fn_exists:
            connection.execute(text("SELECT refresh_zone_statistics()"))


@pytest.fixture
def explain_json(db_engine: Engine) -> Callable[[str, dict[str, Any] | None, bool], dict[str, Any]]:
    """Run EXPLAIN (FORMAT JSON) and return the parsed plan."""

    def _explain(query: str, params: dict[str, Any] | None = None, disable_seqscan: bool = False) -> dict[str, Any]:
        statement = text(f"EXPLAIN (FORMAT JSON) {query}")
        with db_engine.connect() as connection:
            if disable_seqscan:
                connection.execute(text("SET enable_seqscan = off"))
            plan = connection.execute(statement, params or {}).scalar_one()
        return parse_plan(plan)

    return _explain


@pytest.fixture
def listing_factory(db_engine: Engine) -> Callable[..., UUID]:
    """Insert a listing row and return its UUID."""

    def _factory(**overrides: Any) -> UUID:
        listing_id = overrides.pop("id", uuid4())
        country = overrides.pop("country", "ES")
        source = overrides.pop("source", "idealista")
        source_id = overrides.pop("source_id", f"{country.lower()}-{uuid4().hex[:10]}")
        now = datetime.now(timezone.utc)
        params = {
            "id": listing_id,
            "country": country,
            "source": source,
            "source_id": source_id,
            "source_url": overrides.pop("source_url", f"https://example.com/{source_id}"),
            "city": overrides.pop("city", "Madrid"),
            "zone_id": overrides.pop("zone_id", None),
            "asking_price": overrides.pop("asking_price", 250000),
            "asking_price_eur": overrides.pop("asking_price_eur", 250000),
            "price_per_m2_eur": overrides.pop("price_per_m2_eur", 3200),
            "property_category": overrides.pop("property_category", "residential"),
            "status": overrides.pop("status", "active"),
            "description_orig": overrides.pop("description_orig", "Bright city apartment"),
            "published_at": overrides.pop("published_at", now - timedelta(days=7)),
            "first_seen_at": overrides.pop("first_seen_at", now - timedelta(days=7)),
            "last_seen_at": overrides.pop("last_seen_at", now),
            "created_at": overrides.pop("created_at", now),
            "updated_at": overrides.pop("updated_at", now),
            "deal_tier": overrides.pop("deal_tier", 1),
            "lon": overrides.pop("lon", -3.7038),
            "lat": overrides.pop("lat", 40.4168),
        }
        with db_engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO listings (
                        id,
                        country,
                        source,
                        source_id,
                        source_url,
                        city,
                        zone_id,
                        asking_price,
                        asking_price_eur,
                        price_per_m2_eur,
                        property_category,
                        status,
                        description_orig,
                        published_at,
                        first_seen_at,
                        last_seen_at,
                        created_at,
                        updated_at,
                        deal_tier,
                        location
                    )
                    VALUES (
                        :id,
                        :country,
                        :source,
                        :source_id,
                        :source_url,
                        :city,
                        :zone_id,
                        :asking_price,
                        :asking_price_eur,
                        :price_per_m2_eur,
                        :property_category,
                        :status,
                        :description_orig,
                        :published_at,
                        :first_seen_at,
                        :last_seen_at,
                        :created_at,
                        :updated_at,
                        :deal_tier,
                        ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)
                    )
                    """
                ),
                params,
            )
        return listing_id

    return _factory


@pytest.fixture
def price_history_factory(db_engine: Engine) -> Callable[..., int]:
    """Insert a price-history row and return its bigint id."""

    def _factory(**overrides: Any) -> int:
        params = {
            "listing_id": overrides.pop("listing_id", uuid4()),
            "country": overrides.pop("country", "ES"),
            "old_price": overrides.pop("old_price", 250000),
            "new_price": overrides.pop("new_price", 245000),
            "currency": overrides.pop("currency", "EUR"),
            "old_price_eur": overrides.pop("old_price_eur", 250000),
            "new_price_eur": overrides.pop("new_price_eur", 245000),
            "change_type": overrides.pop("change_type", "price_change"),
            "old_status": overrides.pop("old_status", "active"),
            "new_status": overrides.pop("new_status", "active"),
            "recorded_at": overrides.pop("recorded_at", datetime.now(timezone.utc)),
            "source": overrides.pop("source", "pipeline"),
        }
        with db_engine.begin() as connection:
            return int(
                connection.execute(
                    text(
                        """
                        INSERT INTO price_history (
                            listing_id,
                            country,
                            old_price,
                            new_price,
                            currency,
                            old_price_eur,
                            new_price_eur,
                            change_type,
                            old_status,
                            new_status,
                            recorded_at,
                            source
                        )
                        VALUES (
                            :listing_id,
                            :country,
                            :old_price,
                            :new_price,
                            :currency,
                            :old_price_eur,
                            :new_price_eur,
                            :change_type,
                            :old_status,
                            :new_status,
                            :recorded_at,
                            :source
                        )
                        RETURNING id
                        """
                    ),
                    params,
                ).scalar_one()
            )

    return _factory


@pytest.fixture
def user_factory(db_engine: Engine) -> Callable[..., UUID]:
    """Insert a user row and return its UUID."""

    def _factory(**overrides: Any) -> UUID:
        user_id = overrides.pop("id", uuid4())
        email = overrides.pop("email", f"user-{uuid4().hex[:8]}@example.com")
        with db_engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO users (
                        id,
                        email,
                        password_hash,
                        display_name,
                        subscription_tier,
                        alert_limit,
                        email_verified,
                        deleted_at
                    )
                    VALUES (
                        :id,
                        :email,
                        :password_hash,
                        :display_name,
                        :subscription_tier,
                        :alert_limit,
                        :email_verified,
                        :deleted_at
                    )
                    """
                ),
                {
                    "id": user_id,
                    "email": email,
                    "password_hash": overrides.pop("password_hash", "hashed-secret"),
                    "display_name": overrides.pop("display_name", "Schema Test"),
                    "subscription_tier": overrides.pop("subscription_tier", "free"),
                    "alert_limit": overrides.pop("alert_limit", 3),
                    "email_verified": overrides.pop("email_verified", True),
                    "deleted_at": overrides.pop("deleted_at", None),
                },
            )
        return user_id

    return _factory


@pytest.fixture
def alert_rule_factory(db_engine: Engine) -> Callable[..., UUID]:
    """Insert an alert rule and return its UUID."""

    def _factory(**overrides: Any) -> UUID:
        rule_id = overrides.pop("id", uuid4())
        with db_engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO alert_rules (
                        id,
                        user_id,
                        name,
                        filters,
                        channels,
                        active,
                        trigger_count
                    )
                    VALUES (
                        :id,
                        :user_id,
                        :name,
                        CAST(:filters AS jsonb),
                        CAST(:channels AS jsonb),
                        :active,
                        :trigger_count
                    )
                    """
                ),
                {
                    "id": rule_id,
                    "user_id": overrides.pop("user_id"),
                    "name": overrides.pop("name", "Madrid deals"),
                    "filters": json.dumps(overrides.pop("filters", {"country": "ES"})),
                    "channels": json.dumps(overrides.pop("channels", {"email": True})),
                    "active": overrides.pop("active", True),
                    "trigger_count": overrides.pop("trigger_count", 0),
                },
            )
        return rule_id

    return _factory


@pytest.fixture
def zone_factory(db_engine: Engine) -> Callable[..., UUID]:
    """Insert a zone row and return its UUID."""

    def _factory(**overrides: Any) -> UUID:
        zone_id = overrides.pop("id", uuid4())
        geometry_wkt = overrides.pop(
            "geometry_wkt",
            "MULTIPOLYGON(((-3.8 40.3,-3.6 40.3,-3.6 40.5,-3.8 40.5,-3.8 40.3)))",
        )
        bbox_wkt = overrides.pop(
            "bbox_wkt",
            "POLYGON((-3.8 40.3,-3.6 40.3,-3.6 40.5,-3.8 40.5,-3.8 40.3))",
        )
        with db_engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO zones (
                        id,
                        name,
                        name_local,
                        country_code,
                        level,
                        parent_id,
                        geometry,
                        bbox,
                        population,
                        area_km2,
                        slug,
                        osm_id
                    )
                    VALUES (
                        :id,
                        :name,
                        :name_local,
                        :country_code,
                        :level,
                        :parent_id,
                        ST_GeomFromText(:geometry_wkt, 4326),
                        ST_GeomFromText(:bbox_wkt, 4326),
                        :population,
                        :area_km2,
                        :slug,
                        :osm_id
                    )
                    """
                ),
                {
                    "id": zone_id,
                    "name": overrides.pop("name", "Madrid"),
                    "name_local": overrides.pop("name_local", "Madrid"),
                    "country_code": overrides.pop("country_code", "ES"),
                    "level": overrides.pop("level", 3),
                    "parent_id": overrides.pop("parent_id", None),
                    "geometry_wkt": geometry_wkt,
                    "bbox_wkt": bbox_wkt,
                    "population": overrides.pop("population", 3300000),
                    "area_km2": overrides.pop("area_km2", 605.8),
                    "slug": overrides.pop("slug", f"zone-{uuid4().hex[:8]}"),
                    "osm_id": overrides.pop("osm_id", 346905),
                },
            )
        return zone_id

    return _factory


@pytest.fixture
def conversation_factory(db_engine: Engine) -> Callable[..., UUID]:
    """Insert an AI conversation row and return its UUID."""

    def _factory(**overrides: Any) -> UUID:
        conversation_id = overrides.pop("id", uuid4())
        with db_engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO ai_conversations (
                        id,
                        user_id,
                        language,
                        criteria_state,
                        alert_rule_id,
                        turn_count,
                        status,
                        model_used
                    )
                    VALUES (
                        :id,
                        :user_id,
                        :language,
                        CAST(:criteria_state AS jsonb),
                        :alert_rule_id,
                        :turn_count,
                        :status,
                        :model_used
                    )
                    """
                ),
                {
                    "id": conversation_id,
                    "user_id": overrides.pop("user_id", None),
                    "language": overrides.pop("language", "en"),
                    "criteria_state": json.dumps(overrides.pop("criteria_state", {})),
                    "alert_rule_id": overrides.pop("alert_rule_id", None),
                    "turn_count": overrides.pop("turn_count", 0),
                    "status": overrides.pop("status", "active"),
                    "model_used": overrides.pop("model_used", "gpt-5"),
                },
            )
        return conversation_id

    return _factory


@pytest.fixture
def message_factory(db_engine: Engine) -> Callable[..., int]:
    """Insert an AI message row and return its bigint id."""

    def _factory(**overrides: Any) -> int:
        with db_engine.begin() as connection:
            return int(
                connection.execute(
                    text(
                        """
                        INSERT INTO ai_messages (
                            conversation_id,
                            role,
                            content,
                            criteria_snapshot,
                            visual_refs,
                            tokens_used
                        )
                        VALUES (
                            :conversation_id,
                            :role,
                            :content,
                            CAST(:criteria_snapshot AS jsonb),
                            CAST(:visual_refs AS jsonb),
                            :tokens_used
                        )
                        RETURNING id
                        """
                    ),
                    {
                        "conversation_id": overrides.pop("conversation_id"),
                        "role": overrides.pop("role", "user"),
                        "content": overrides.pop("content", "Find me a flat"),
                        "criteria_snapshot": json.dumps(overrides.pop("criteria_snapshot", {})),
                        "visual_refs": json.dumps(overrides.pop("visual_refs", [])),
                        "tokens_used": overrides.pop("tokens_used", 128),
                    },
                ).scalar_one()
            )

    return _factory


@pytest.fixture
def ml_model_factory(db_engine: Engine) -> Callable[..., UUID]:
    """Insert an ML model row and return its UUID."""

    def _factory(**overrides: Any) -> UUID:
        model_id = overrides.pop("id", uuid4())
        with db_engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO ml_model_versions (
                        id,
                        country_code,
                        algorithm,
                        version_tag,
                        artifact_path,
                        dataset_ref,
                        feature_names,
                        metrics,
                        status
                    )
                    VALUES (
                        :id,
                        :country_code,
                        :algorithm,
                        :version_tag,
                        :artifact_path,
                        :dataset_ref,
                        CAST(:feature_names AS jsonb),
                        CAST(:metrics AS jsonb),
                        :status
                    )
                    """
                ),
                {
                    "id": model_id,
                    "country_code": overrides.pop("country_code", "ES"),
                    "algorithm": overrides.pop("algorithm", "lightgbm"),
                    "version_tag": overrides.pop("version_tag", f"es-model-{uuid4().hex[:8]}"),
                    "artifact_path": overrides.pop("artifact_path", "models/es-model.onnx"),
                    "dataset_ref": overrides.pop("dataset_ref", "datasets/es-train.parquet"),
                    "feature_names": json.dumps(overrides.pop("feature_names", ["price_per_m2_eur", "bedrooms"])),
                    "metrics": json.dumps(overrides.pop("metrics", {"mae": 15000, "rmse": 22000, "r2": 0.87})),
                    "status": overrides.pop("status", "staging"),
                },
            )
        return model_id

    return _factory
