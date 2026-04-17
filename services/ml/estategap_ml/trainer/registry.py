"""Model-registry persistence and promotion helpers."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
import re
from typing import Any
from uuid import UUID

import asyncpg
import boto3
from estategap_common.models import MlModelVersion, ModelStatus

from estategap_ml.config import Config
from estategap_ml.trainer.evaluate import Metrics


VERSION_RE = re.compile(r"_v(?P<version>\d+)$")


def build_minio_client(config: Config) -> Any:
    """Build an S3-compatible client for MinIO."""

    return boto3.client(
        "s3",
        endpoint_url=config.minio_endpoint,
        aws_access_key_id=config.minio_access_key,
        aws_secret_access_key=config.minio_secret_key,
    )


def _row_to_model(row: asyncpg.Record | None) -> MlModelVersion | None:
    if row is None:
        return None
    payload = dict(row)
    payload["status"] = ModelStatus(payload["status"])
    return MlModelVersion.model_validate(payload)


async def get_active_champion(country: str, conn: asyncpg.Connection) -> MlModelVersion | None:
    """Fetch the currently active champion for a country and lock it."""

    row = await conn.fetchrow(
        """
        SELECT *
        FROM model_versions
        WHERE country_code = $1 AND status = 'active'
        FOR UPDATE
        """,
        country.upper(),
    )
    return _row_to_model(row)


async def get_champion_for_country(country: str, conn: asyncpg.Connection) -> MlModelVersion | None:
    """Compatibility alias for champion lookup."""

    return await get_active_champion(country=country, conn=conn)


async def next_version_tag(country: str, city_scope: str, conn: asyncpg.Connection) -> str:
    """Return the next sequential model version tag for a country/scope."""

    prefix = f"{country.lower()}_{city_scope}_v"
    row = await conn.fetchrow(
        """
        SELECT version_tag
        FROM model_versions
        WHERE country_code = $1
          AND version_tag LIKE $2
        ORDER BY created_at DESC
        LIMIT 1
        """,
        country.upper(),
        f"{prefix}%",
    )
    current = 0
    if row is not None:
        match = VERSION_RE.search(row["version_tag"])
        if match is not None:
            current = int(match.group("version"))
    return f"{prefix}{current + 1}"


async def insert_staging_version(
    metrics: Metrics | dict[str, Any],
    artifact_path: str,
    fe_path: str,
    version_tag: str,
    country: str,
    conn: asyncpg.Connection,
    feature_names: list[str] | None = None,
    dataset_ref: str | None = None,
    transfer_learned: bool = False,
    base_country: str | None = None,
    confidence: str = "full",
) -> UUID:
    """Insert a new challenger row in staging status."""

    payload = metrics.to_dict() if isinstance(metrics, Metrics) else metrics
    return await conn.fetchval(
        """
        INSERT INTO model_versions (
            country_code,
            algorithm,
            version_tag,
            artifact_path,
            dataset_ref,
            feature_names,
            metrics,
            status,
            transfer_learned,
            base_country,
            confidence,
            trained_at,
            created_at
        )
        VALUES ($1, 'lightgbm', $2, $3, $4, $5, $6::jsonb, 'staging', $7, $8, $9, $10, $10)
        RETURNING id
        """,
        country.upper(),
        version_tag,
        artifact_path,
        dataset_ref or fe_path,
        feature_names or [],
        payload,
        transfer_learned,
        base_country.upper() if base_country else None,
        confidence,
        datetime.now(tz=UTC),
    )


async def promote_version(
    new_id: UUID,
    champion_id: UUID | None,
    conn: asyncpg.Connection,
) -> None:
    """Promote a challenger and retire the existing champion atomically."""

    now = datetime.now(tz=UTC)
    if champion_id is not None:
        await conn.execute(
            """
            UPDATE model_versions
            SET status = 'retired', retired_at = $2
            WHERE id = $1
            """,
            champion_id,
            now,
        )
    await conn.execute(
        """
        UPDATE model_versions
        SET status = 'active', promoted_at = $2
        WHERE id = $1
        """,
        new_id,
        now,
    )


def upload_artifacts(
    onnx_path: Path,
    fe_path: Path,
    minio_client: Any,
    bucket: str,
    version_tag: str,
) -> str:
    """Upload the exported artefacts to MinIO and return the ONNX object URI."""

    onnx_key = f"models/{version_tag}.onnx"
    fe_key = f"models/{version_tag}_feature_engineer.joblib"
    minio_client.upload_file(str(onnx_path), bucket, onnx_key)
    minio_client.upload_file(str(fe_path), bucket, fe_key)
    return f"s3://{bucket}/{onnx_key}"


async def maybe_promote(
    country: str,
    challenger_metrics: Metrics,
    onnx_path: Path,
    fe_path: Path,
    config: Config,
    *,
    version_tag: str,
    feature_names: list[str] | None = None,
    dataset_ref: str | None = None,
    transfer_learned: bool = False,
    base_country: str | None = None,
    confidence: str = "full",
    dry_run: bool = False,
    minio_client: Any | None = None,
) -> bool:
    """Compare a challenger to the active champion and promote if it clears the threshold."""

    artifact_path = str(onnx_path)
    if not dry_run:
        client = minio_client or build_minio_client(config)
        artifact_path = upload_artifacts(
            onnx_path=onnx_path,
            fe_path=fe_path,
            minio_client=client,
            bucket=config.minio_bucket,
            version_tag=version_tag,
            )

    conn = await asyncpg.connect(config.database_url)
    try:
        async with conn.transaction():
            champion = await get_active_champion(country=country, conn=conn)
            if dry_run:
                return False
            challenger_id = await insert_staging_version(
                metrics=challenger_metrics,
                artifact_path=artifact_path,
                fe_path=str(fe_path),
                version_tag=version_tag,
                country=country,
                conn=conn,
                feature_names=feature_names,
                dataset_ref=dataset_ref,
                transfer_learned=transfer_learned,
                base_country=base_country,
                confidence=confidence,
            )
            if champion is None:
                await promote_version(new_id=challenger_id, champion_id=champion.id if champion else None, conn=conn)
                return True

            champion_mape = float(champion.metrics.get("mape_national", 1.0))
            improvement_target = champion_mape * (1.0 - config.promotion_mape_improvement_pct)
            promoted = challenger_metrics.mape_national < improvement_target
            if promoted:
                await promote_version(new_id=challenger_id, champion_id=champion.id, conn=conn)
            else:
                await conn.execute(
                    """
                    UPDATE model_versions
                    SET status = 'retired', retired_at = $2
                    WHERE id = $1
                    """,
                    challenger_id,
                    datetime.now(tz=UTC),
                )
            return promoted
    finally:
        await conn.close()


__all__ = [
    "build_minio_client",
    "get_active_champion",
    "get_champion_for_country",
    "insert_staging_version",
    "maybe_promote",
    "next_version_tag",
    "promote_version",
    "upload_artifacts",
]
