from __future__ import annotations

import time
from uuid import uuid4

import pytest

pytest.importorskip("asyncpg")
pytest.importorskip("boto3")
pytest.importorskip("lightgbm")
pytest.importorskip("mlflow")
pytest.importorskip("pydantic_settings")
pytest.importorskip("testcontainers")

import asyncpg
import boto3
from testcontainers.core.container import DockerContainer
from testcontainers.postgres import PostgresContainer

from estategap_ml.config import Config
from estategap_ml.trainer.train import run_training


def _asyncpg_dsn(sqlalchemy_dsn: str) -> str:
    return sqlalchemy_dsn.replace("postgresql+psycopg2://", "postgresql://", 1)


async def _prepare_database(dsn: str) -> None:
    conn = await asyncpg.connect(dsn)
    try:
        await conn.execute(
            """
            CREATE EXTENSION IF NOT EXISTS postgis;
            CREATE EXTENSION IF NOT EXISTS pgcrypto;
            CREATE TABLE zones (
                id UUID PRIMARY KEY,
                country_code CHAR(2) NOT NULL,
                name TEXT NOT NULL
            );
            CREATE TABLE listings (
                id UUID PRIMARY KEY,
                country CHAR(2) NOT NULL,
                city TEXT,
                zone_id UUID,
                location geometry(POINT, 4326),
                asking_price_eur NUMERIC,
                price_per_m2_eur NUMERIC,
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
                days_on_market INTEGER,
                published_at TIMESTAMPTZ,
                status TEXT,
                dist_metro_m INTEGER,
                dist_train_m INTEGER,
                dist_beach_m INTEGER,
                data_completeness NUMERIC,
                created_at TIMESTAMPTZ DEFAULT NOW()
            );
            CREATE MATERIALIZED VIEW zone_statistics AS
            SELECT
                zone_id,
                country AS country_code,
                COUNT(*) AS listing_count,
                COUNT(*) AS active_listings,
                PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY price_per_m2_eur) AS median_price_m2_eur
            FROM listings
            WHERE zone_id IS NOT NULL
            GROUP BY zone_id, country;
            CREATE TABLE model_versions (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                country_code CHAR(2) NOT NULL,
                algorithm VARCHAR(50) NOT NULL DEFAULT 'lightgbm',
                version_tag VARCHAR(100) NOT NULL,
                artifact_path TEXT NOT NULL,
                dataset_ref TEXT,
                feature_names JSONB NOT NULL DEFAULT '[]'::jsonb,
                metrics JSONB NOT NULL DEFAULT '{}'::jsonb,
                status VARCHAR(20) NOT NULL DEFAULT 'staging',
                trained_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                promoted_at TIMESTAMPTZ,
                retired_at TIMESTAMPTZ,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
            CREATE UNIQUE INDEX uq_model_versions_country_version_tag
                ON model_versions (country_code, version_tag);
            CREATE INDEX ix_model_versions_country_code_status
                ON model_versions (country_code, status);
            """
        )
        zone_id = uuid4()
        await conn.execute(
            "INSERT INTO zones (id, country_code, name) VALUES ($1, 'ES', 'Madrid Centro')",
            zone_id,
        )
        records = []
        for idx in range(10_000):
            records.append(
                (
                    uuid4(),
                    "ES",
                    "Madrid",
                    zone_id,
                    f"POINT({-3.70 + (idx % 10) * 0.001} {40.40 + (idx % 10) * 0.001})",
                    300000 + idx,
                    3500 + (idx % 250),
                    90 + (idx % 15),
                    80 + (idx % 10),
                    2 + (idx % 3),
                    1 + (idx % 2),
                    2 + (idx % 5),
                    8,
                    True,
                    idx % 2,
                    "apartment",
                    "residential",
                    "B",
                    "good",
                    2010,
                    10,
                    45,
                    "2025-06-01T00:00:00Z",
                    "sold",
                    250,
                    500,
                    10000,
                    0.95,
                )
            )
        await conn.executemany(
            """
            INSERT INTO listings (
                id, country, city, zone_id, location, asking_price_eur, price_per_m2_eur,
                built_area_m2, usable_area_m2, bedrooms, bathrooms, floor_number, total_floors,
                has_lift, parking_spaces, property_type, property_category, energy_rating, condition,
                year_built, images_count, days_on_market, published_at, status,
                dist_metro_m, dist_train_m, dist_beach_m, data_completeness
            )
            VALUES (
                $1, $2, $3, $4, ST_GeomFromText($5, 4326), $6, $7, $8, $9, $10, $11, $12, $13,
                $14, $15, $16, $17, $18, $19, $20, $21, $22, $23, $24, $25, $26, $27, $28
            )
            """,
            records,
        )
        await conn.execute("REFRESH MATERIALIZED VIEW zone_statistics")
    finally:
        await conn.close()


def _minio_client(endpoint: str):
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id="minioadmin",
        aws_secret_access_key="minioadmin",
    )


@pytest.mark.asyncio
async def test_full_pipeline_end_to_end(tmp_path) -> None:
    minio = (
        DockerContainer("minio/minio:latest")
        .with_exposed_ports(9000)
        .with_env("MINIO_ROOT_USER", "minioadmin")
        .with_env("MINIO_ROOT_PASSWORD", "minioadmin")
        .with_command("server /data")
    )
    with PostgresContainer("postgis/postgis:16-3.4") as postgres, minio:
        dsn = _asyncpg_dsn(postgres.get_connection_url())
        endpoint = f"http://{minio.get_container_host_ip()}:{minio.get_exposed_port(9000)}"
        await _prepare_database(dsn)
        client = _minio_client(endpoint)
        deadline = time.time() + 30
        while True:
            try:
                client.list_buckets()
                break
            except Exception:
                if time.time() > deadline:
                    raise
                time.sleep(1)
        client.create_bucket(Bucket="estategap-models")

        config = Config(
            DATABASE_URL=dsn,
            MLFLOW_TRACKING_URI=f"file://{tmp_path / 'mlruns'}",
            KAFKA_BROKERS="localhost:9092",
            KAFKA_TOPIC_PREFIX="estategap.",
            KAFKA_MAX_RETRIES=3,
            MINIO_ENDPOINT=endpoint,
            MINIO_ACCESS_KEY="minioadmin",
            MINIO_SECRET_KEY="minioadmin",
            MINIO_BUCKET="estategap-models",
            OPTUNA_N_TRIALS=2,
            LOCAL_ARTIFACT_DIR=tmp_path / "artifacts",
        )

        result = await run_training("es", config)

        conn = await asyncpg.connect(dsn)
        try:
            active_count = await conn.fetchval(
                "SELECT COUNT(*) FROM model_versions WHERE country_code = 'ES' AND status = 'active'"
            )
        finally:
            await conn.close()

        objects = client.list_objects_v2(Bucket="estategap-models")
        assert result.promoted is True
        assert active_count == 1
        assert "Contents" in objects
        assert (tmp_path / "mlruns").exists()
