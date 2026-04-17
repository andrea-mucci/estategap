from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest

pytest.importorskip("asyncpg")
pytest.importorskip("boto3")
pytest.importorskip("pydantic_settings")
pytest.importorskip("testcontainers")

import asyncpg
from testcontainers.postgres import PostgresContainer

from estategap_ml.config import Config
from estategap_ml.trainer.evaluate import Metrics
from estategap_ml.trainer.registry import get_active_champion, maybe_promote, promote_version


class _NoopMinioClient:
    def upload_file(self, filename: str, bucket: str, key: str) -> None:
        return None


def _asyncpg_dsn(sqlalchemy_dsn: str) -> str:
    return sqlalchemy_dsn.replace("postgresql+psycopg2://", "postgresql://", 1)


async def _create_registry_schema(dsn: str) -> None:
    conn = await asyncpg.connect(dsn)
    try:
        await conn.execute(
            """
            CREATE EXTENSION IF NOT EXISTS pgcrypto;
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
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_promote_version_keeps_single_active_row(tmp_path) -> None:
    with PostgresContainer("postgres:16") as postgres:
        dsn = _asyncpg_dsn(postgres.get_connection_url())
        await _create_registry_schema(dsn)
        conn = await asyncpg.connect(dsn)
        try:
            champion_id = await conn.fetchval(
                """
                INSERT INTO model_versions (country_code, version_tag, artifact_path, metrics, status, trained_at)
                VALUES ('ES', 'es_national_v1', 's3://bucket/es_national_v1.onnx', '{"mape_national": 0.12}'::jsonb, 'active', NOW())
                RETURNING id
                """
            )
            challenger_id = await conn.fetchval(
                """
                INSERT INTO model_versions (country_code, version_tag, artifact_path, metrics, status, trained_at)
                VALUES ('ES', 'es_national_v2', 's3://bucket/es_national_v2.onnx', '{"mape_national": 0.09}'::jsonb, 'staging', NOW())
                RETURNING id
                """
            )
            await promote_version(challenger_id, champion_id, conn)
            active_count = await conn.fetchval(
                "SELECT COUNT(*) FROM model_versions WHERE country_code='ES' AND status='active'"
            )
            assert active_count == 1
        finally:
            await conn.close()


@pytest.mark.asyncio
async def test_maybe_promote_respects_threshold(tmp_path) -> None:
    with PostgresContainer("postgres:16") as postgres:
        dsn = _asyncpg_dsn(postgres.get_connection_url())
        await _create_registry_schema(dsn)
        conn = await asyncpg.connect(dsn)
        try:
            await conn.execute(
                """
                INSERT INTO model_versions (country_code, version_tag, artifact_path, metrics, status, trained_at, promoted_at)
                VALUES ('ES', 'es_national_v1', 's3://bucket/es_national_v1.onnx', '{"mape_national": 0.10}'::jsonb, 'active', NOW(), NOW())
                """
            )
        finally:
            await conn.close()

        config = Config(
            DATABASE_URL=dsn,
            MLFLOW_TRACKING_URI="file:///tmp/mlruns",
            NATS_URL="nats://localhost:4222",
            MINIO_ENDPOINT="http://localhost:9000",
            MINIO_ACCESS_KEY="minioadmin",
            MINIO_SECRET_KEY="minioadmin",
            MINIO_BUCKET="estategap-models",
            OPTUNA_N_TRIALS=1,
        )
        metrics = Metrics(mape_national=0.099, mae_national=1.0, r2_national=0.9, per_city={})
        promoted = await maybe_promote(
            country="es",
            challenger_metrics=metrics,
            onnx_path=tmp_path / "model.onnx",
            fe_path=tmp_path / "engineer.joblib",
            config=config,
            version_tag="es_national_v2",
            dry_run=False,
            minio_client=_NoopMinioClient(),
        )
        conn = await asyncpg.connect(dsn)
        try:
            champion = await get_active_champion("es", conn)
            assert promoted is False
            assert champion is not None
            assert champion.version_tag == "es_national_v1"
        finally:
            await conn.close()


@pytest.mark.asyncio
async def test_maybe_promote_promotes_first_run_and_clear_win(tmp_path) -> None:
    with PostgresContainer("postgres:16") as postgres:
        dsn = _asyncpg_dsn(postgres.get_connection_url())
        await _create_registry_schema(dsn)
        config = Config(
            DATABASE_URL=dsn,
            MLFLOW_TRACKING_URI="file:///tmp/mlruns",
            NATS_URL="nats://localhost:4222",
            MINIO_ENDPOINT="http://localhost:9000",
            MINIO_ACCESS_KEY="minioadmin",
            MINIO_SECRET_KEY="minioadmin",
            MINIO_BUCKET="estategap-models",
            OPTUNA_N_TRIALS=1,
        )
        metrics = Metrics(mape_national=0.07, mae_national=1.0, r2_national=0.9, per_city={})
        promoted = await maybe_promote(
            country="es",
            challenger_metrics=metrics,
            onnx_path=tmp_path / "model.onnx",
            fe_path=tmp_path / "engineer.joblib",
            config=config,
            version_tag="es_national_v1",
            dry_run=False,
            minio_client=_NoopMinioClient(),
        )
        conn = await asyncpg.connect(dsn)
        try:
            champion = await get_active_champion("es", conn)
            assert promoted is True
            assert champion is not None
            assert champion.version_tag == "es_national_v1"
        finally:
            await conn.close()
