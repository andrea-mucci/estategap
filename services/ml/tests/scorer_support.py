from __future__ import annotations

from datetime import UTC, datetime
import json
from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4


def asyncpg_dsn(sqlalchemy_dsn: str) -> str:
    return sqlalchemy_dsn.replace("postgresql+psycopg2://", "postgresql://", 1)


class FakeSession:
    def __init__(self, output: float) -> None:
        self._output = float(output)

    def get_inputs(self) -> list[SimpleNamespace]:
        return [SimpleNamespace(name="features")]

    def run(self, output_names: Any, inputs: dict[str, Any]) -> list[Any]:
        import numpy as np

        batch_size = len(next(iter(inputs.values())))
        return [np.full((batch_size,), self._output, dtype=np.float32)]


class FakeFeatureEngineer:
    def __init__(self, feature_names: list[str] | None = None) -> None:
        self._feature_names = feature_names or ["asking_price_eur", "built_area_m2", "bedrooms"]

    def transform(self, frame: Any) -> Any:
        import numpy as np
        import pandas as pd

        if not isinstance(frame, pd.DataFrame):
            frame = pd.DataFrame(frame)
        rows = []
        for _, row in frame.iterrows():
            rows.append([float(row.get(name, 0.0) or 0.0) for name in self._feature_names])
        return np.asarray(rows, dtype=np.float32)

    def get_feature_names_out(self) -> list[str]:
        return list(self._feature_names)


def build_fake_bundle(
    *,
    version_tag: str = "es_national_v1",
    country_code: str = "es",
    point: float = 245000.0,
    q05: float = 210000.0,
    q95: float = 280000.0,
    feature_names: list[str] | None = None,
    lgb_booster: Any | None = None,
) -> Any:
    engineer = FakeFeatureEngineer(feature_names)
    return SimpleNamespace(
        country_code=country_code,
        version_tag=version_tag,
        session_point=FakeSession(point),
        session_q05=FakeSession(q05),
        session_q95=FakeSession(q95),
        lgb_booster=lgb_booster or object(),
        feature_engineer=engineer,
        input_name="features",
        feature_names=engineer.get_feature_names_out(),
        loaded_at=datetime.now(tz=UTC),
    )


def make_listing(**overrides: Any) -> dict[str, Any]:
    listing = {
        "id": overrides.pop("id", uuid4()),
        "country": overrides.pop("country", "ES"),
        "zone_id": overrides.pop("zone_id", uuid4()),
        "city": overrides.pop("city", "Madrid"),
        "asking_price_eur": overrides.pop("asking_price_eur", 199500.0),
        "asking_price": overrides.pop("asking_price", 199500.0),
        "built_area_m2": overrides.pop("built_area_m2", 85.0),
        "usable_area_m2": overrides.pop("usable_area_m2", 80.0),
        "bedrooms": overrides.pop("bedrooms", 3),
        "bathrooms": overrides.pop("bathrooms", 2),
        "floor_number": overrides.pop("floor_number", 4),
        "total_floors": overrides.pop("total_floors", 8),
        "has_lift": overrides.pop("has_lift", True),
        "parking_spaces": overrides.pop("parking_spaces", 1),
        "property_type": overrides.pop("property_type", "apartment"),
        "property_category": overrides.pop("property_category", "residential"),
        "energy_rating": overrides.pop("energy_rating", "B"),
        "condition": overrides.pop("condition", "good"),
        "year_built": overrides.pop("year_built", 2012),
        "images_count": overrides.pop("images_count", 8),
        "published_at": overrides.pop("published_at", "2026-04-01T00:00:00Z"),
        "status": overrides.pop("status", "active"),
        "dist_metro_m": overrides.pop("dist_metro_m", 250),
        "dist_train_m": overrides.pop("dist_train_m", 600),
        "dist_beach_m": overrides.pop("dist_beach_m", 12000),
        "lat": overrides.pop("lat", 40.4168),
        "lon": overrides.pop("lon", -3.7038),
        "created_at": overrides.pop("created_at", datetime(2026, 4, 1, tzinfo=UTC)),
        "updated_at": overrides.pop("updated_at", datetime(2026, 4, 1, tzinfo=UTC)),
    }
    listing.update(overrides)
    return listing


async def prepare_scorer_database(
    dsn: str,
    listings: list[dict[str, Any]],
    *,
    include_model_versions: bool = False,
) -> None:
    import asyncpg

    conn = await asyncpg.connect(dsn)
    try:
        await conn.execute(
            """
            CREATE EXTENSION IF NOT EXISTS postgis;
            CREATE EXTENSION IF NOT EXISTS pgcrypto;
            DROP TABLE IF EXISTS model_versions;
            DROP TABLE IF EXISTS listings;
            CREATE TABLE listings (
                id UUID PRIMARY KEY,
                country CHAR(2) NOT NULL,
                zone_id UUID,
                city TEXT,
                location geometry(POINT, 4326),
                asking_price NUMERIC,
                asking_price_eur NUMERIC,
                built_area_m2 NUMERIC,
                usable_area_m2 NUMERIC,
                bedrooms SMALLINT,
                bathrooms SMALLINT,
                floor_number SMALLINT,
                total_floors SMALLINT,
                has_lift BOOLEAN,
                parking_spaces SMALLINT,
                property_type TEXT,
                property_category TEXT,
                energy_rating CHAR(1),
                condition TEXT,
                year_built SMALLINT,
                images_count SMALLINT,
                published_at TIMESTAMPTZ,
                status TEXT,
                dist_metro_m INTEGER,
                dist_train_m INTEGER,
                dist_beach_m INTEGER,
                estimated_price_eur NUMERIC(14, 2),
                deal_score NUMERIC(6, 2),
                deal_tier SMALLINT,
                confidence_low_eur NUMERIC(14, 2),
                confidence_high_eur NUMERIC(14, 2),
                model_version VARCHAR(100),
                scored_at TIMESTAMPTZ,
                shap_features JSONB NOT NULL DEFAULT '[]'::jsonb,
                comparable_ids UUID[],
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            );
            """
        )
        if include_model_versions:
            await conn.execute(
                """
                CREATE TABLE model_versions (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    country_code CHAR(2) NOT NULL,
                    version_tag VARCHAR(100) NOT NULL,
                    artifact_path TEXT NOT NULL,
                    feature_names JSONB NOT NULL DEFAULT '[]'::jsonb,
                    status VARCHAR(20) NOT NULL DEFAULT 'staging',
                    trained_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                CREATE UNIQUE INDEX uq_model_versions_country_version_tag
                    ON model_versions (country_code, version_tag);
                """
            )
        await conn.executemany(
            """
            INSERT INTO listings (
                id, country, zone_id, city, location, asking_price, asking_price_eur, built_area_m2,
                usable_area_m2, bedrooms, bathrooms, floor_number, total_floors, has_lift, parking_spaces,
                property_type, property_category, energy_rating, condition, year_built, images_count,
                published_at, status, dist_metro_m, dist_train_m, dist_beach_m, created_at, updated_at
            )
            VALUES (
                $1, $2, $3, $4, ST_GeomFromText($5, 4326), $6, $7, $8,
                $9, $10, $11, $12, $13, $14, $15,
                $16, $17, $18, $19, $20, $21,
                $22, $23, $24, $25, $26, $27, $28
            )
            """,
            [
                (
                    listing["id"],
                    listing["country"],
                    listing["zone_id"],
                    listing["city"],
                    f"POINT({listing['lon']} {listing['lat']})",
                    listing["asking_price"],
                    listing["asking_price_eur"],
                    listing["built_area_m2"],
                    listing["usable_area_m2"],
                    listing["bedrooms"],
                    listing["bathrooms"],
                    listing["floor_number"],
                    listing["total_floors"],
                    listing["has_lift"],
                    listing["parking_spaces"],
                    listing["property_type"],
                    listing["property_category"],
                    listing["energy_rating"],
                    listing["condition"],
                    listing["year_built"],
                    listing["images_count"],
                    listing["published_at"],
                    listing["status"],
                    listing["dist_metro_m"],
                    listing["dist_train_m"],
                    listing["dist_beach_m"],
                    listing["created_at"],
                    listing["updated_at"],
                )
                for listing in listings
            ],
        )
    finally:
        await conn.close()


async def seed_model_version(
    dsn: str,
    *,
    country_code: str,
    version_tag: str,
    artifact_path: str,
    status: str = "active",
    feature_names: list[str] | None = None,
) -> None:
    import asyncpg

    conn = await asyncpg.connect(dsn)
    try:
        await conn.execute(
            """
            INSERT INTO model_versions (country_code, version_tag, artifact_path, feature_names, status, trained_at, created_at)
            VALUES ($1, $2, $3, $4::jsonb, $5, NOW(), NOW())
            """,
            country_code.upper(),
            version_tag,
            artifact_path,
            json.dumps(feature_names or []),
            status,
        )
    finally:
        await conn.close()
