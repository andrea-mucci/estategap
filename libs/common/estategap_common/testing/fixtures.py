from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import asyncpg  # type: ignore[import-untyped]
import pytest
from alembic import command
from alembic.config import Config


REPO_ROOT = Path(__file__).resolve().parents[4]
PIPELINE_ROOT = REPO_ROOT / "services" / "pipeline"


def _import_postgres_container() -> type[Any]:
    pytest.importorskip("testcontainers.postgres")
    from testcontainers.postgres import PostgresContainer

    return PostgresContainer


def _import_redis_container() -> type[Any]:
    pytest.importorskip("testcontainers.redis")
    from testcontainers.redis import RedisContainer

    return RedisContainer


def _import_docker_container() -> type[Any]:
    pytest.importorskip("testcontainers.core.container")
    from testcontainers.core.container import DockerContainer

    return DockerContainer


@pytest.fixture(scope="session")
def postgres_container() -> Iterator[Any]:
    PostgresContainer = _import_postgres_container()
    container = PostgresContainer("postgis/postgis:16-3.4")
    try:
        container.start()
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"Docker is not available for PostgreSQL integration tests: {exc}")

    try:
        sqlalchemy_url = container.get_connection_url()
        _run_migrations(sqlalchemy_url)
        yield container
    finally:
        container.stop()


@pytest.fixture
async def db_pool(postgres_container: Any) -> AsyncIterator[asyncpg.Pool]:
    database_url = postgres_container.get_connection_url().replace("+psycopg2", "")
    pool = await asyncpg.create_pool(database_url, min_size=1, max_size=4, command_timeout=30)
    await _reset_database(pool)
    try:
        yield pool
    finally:
        await _reset_database(pool)
        await pool.close()


@pytest.fixture(scope="session")
def redis_container() -> Iterator[Any]:
    RedisContainer = _import_redis_container()
    container = RedisContainer("redis:7-alpine")
    try:
        container.start()
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"Docker is not available for Redis integration tests: {exc}")

    try:
        yield container
    finally:
        container.stop()


@pytest.fixture
async def redis_client(redis_container: Any) -> AsyncIterator[Any]:
    import redis.asyncio as redis  # type: ignore[import-untyped]

    client = redis.from_url(redis_container.get_connection_url(), decode_responses=True)
    await client.flushdb()
    try:
        yield client
    finally:
        await client.flushdb()
        await client.aclose()


@pytest.fixture(scope="session")
def kafka_container() -> Iterator[Any]:
    pytest.importorskip("testcontainers.kafka")
    from testcontainers.kafka import KafkaContainer

    container = KafkaContainer("confluentinc/cp-kafka:7.6.1")
    try:
        container.start()
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"Docker is not available for Kafka integration tests: {exc}")

    try:
        yield container
    finally:
        container.stop()


@pytest.fixture
async def kafka_client(kafka_container: Any) -> AsyncIterator[Any]:
    pytest.importorskip("aiokafka")
    from aiokafka import AIOKafkaConsumer

    client = AIOKafkaConsumer(
        bootstrap_servers=kafka_container.get_bootstrap_server(),
        group_id="estategap-common-test-client",
        enable_auto_commit=False,
        auto_offset_reset="latest",
    )
    await client.start()
    try:
        yield client
    finally:
        await client.stop()


@pytest.fixture(scope="session")
def minio_container() -> Iterator[dict[str, str | Any]]:
    DockerContainer = _import_docker_container()
    container = (
        DockerContainer("minio/minio:latest")
        .with_env("MINIO_ROOT_USER", "minioadmin")
        .with_env("MINIO_ROOT_PASSWORD", "minioadmin")
        .with_exposed_ports(9000)
        .with_command("server /data --console-address :9001")
    )
    try:
        container.start()
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"Docker is not available for MinIO integration tests: {exc}")

    try:
        yield {
            "container": container,
            "endpoint_url": f"http://{container.get_container_host_ip()}:{container.get_exposed_port(9000)}",
            "access_key": "minioadmin",
            "secret_key": "minioadmin",
        }
    finally:
        container.stop()


@pytest.fixture
def minio_client(minio_container: dict[str, str | Any]) -> Iterator[Any]:
    import boto3

    client = boto3.client(
        "s3",
        endpoint_url=str(minio_container["endpoint_url"]),
        aws_access_key_id=str(minio_container["access_key"]),
        aws_secret_access_key=str(minio_container["secret_key"]),
        region_name="us-east-1",
    )
    try:
        yield client
    finally:
        client.close()


def _run_migrations(sqlalchemy_url: str) -> None:
    alembic_cfg = Config(str(PIPELINE_ROOT / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(PIPELINE_ROOT / "alembic"))
    alembic_cfg.set_main_option("sqlalchemy.url", sqlalchemy_url)
    command.upgrade(alembic_cfg, "head")


async def _reset_database(pool: asyncpg.Pool) -> None:
    async with pool.acquire() as conn:
        tables = await conn.fetch(
            """
            SELECT tablename
            FROM pg_tables
            WHERE schemaname = 'public'
              AND tablename <> 'alembic_version'
            ORDER BY tablename
            """
        )
        if tables:
            table_list = ", ".join(f'"{row["tablename"]}"' for row in tables)
            await conn.execute(f"TRUNCATE TABLE {table_list} RESTART IDENTITY CASCADE")

        has_exchange_rates = await conn.fetchval(
            """
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_name = 'exchange_rates'
            )
            """
        )
        if has_exchange_rates:
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


__all__ = [
    "db_pool",
    "kafka_client",
    "kafka_container",
    "minio_client",
    "minio_container",
    "postgres_container",
    "redis_client",
    "redis_container",
]
