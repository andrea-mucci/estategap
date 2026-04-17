"""CLI entry point for the ML scorer service."""

from __future__ import annotations

import asyncio

import asyncpg
import boto3
from estategap_common.logging import configure_logging
import nats

from estategap_ml import Config, logger

from .comparables import ComparablesFinder
from .metrics import start_http_server
from .model_registry import ModelRegistry
from .server import serve
from .shap_explainer import ShapExplainer


async def main() -> int:
    config = Config()
    configure_logging(level=config.log_level, service="ml-scorer")
    start_http_server(config.prometheus_port)
    db_pool = None
    nc = None
    try:
        db_pool = await asyncpg.create_pool(config.database_url)
        s3_client = boto3.client(
            "s3",
            endpoint_url=config.minio_endpoint,
            aws_access_key_id=config.minio_access_key,
            aws_secret_access_key=config.minio_secret_key,
        )
        nc = await nats.connect(config.nats_url)
        js = nc.jetstream()
        shap_explainer = ShapExplainer(timeout_seconds=config.shap_timeout_seconds)
        registry = ModelRegistry(
            bucket=config.minio_bucket,
            s3_client=s3_client,
            poll_interval_seconds=config.model_poll_interval_seconds,
            shap_explainer=shap_explainer,
        )
        await registry.load_active_models(db_pool)
        if not registry.bundles:
            logger.error("no_active_models_loaded")
            return 1
        comparables_finder = ComparablesFinder(
            refresh_interval_seconds=config.comparables_refresh_interval_seconds,
            registry=registry,
        )
        await comparables_finder.refresh_zone_indices(db_pool)
        await serve(
            config,
            registry,
            db_pool,
            js,
            nats_connection=nc,
            shap_explainer=shap_explainer,
            comparables_finder=comparables_finder,
        )
        return 0
    finally:
        if nc is not None:
            await nc.drain()
        if db_pool is not None:
            await db_pool.close()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
