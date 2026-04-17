"""CLI entry point for the ML scorer service."""

from __future__ import annotations

import asyncio

import asyncpg
import boto3
from estategap_common.broker import KafkaBroker, KafkaConfig
from estategap_common.broker.kafka_lag import start_lag_poller
from estategap_common.logging import configure_logging

from estategap_ml import Config, logger

from .comparables import ComparablesFinder
from .kafka_consumer import CONSUMER_GROUP, INPUT_TOPIC
from .metrics import start_http_server
from .model_registry import ModelRegistry
from .server import serve
from .shap_explainer import ShapExplainer


async def main() -> int:
    config = Config()
    configure_logging(level=config.log_level, service="ml-scorer")
    start_http_server(config.prometheus_port)
    db_pool = None
    broker = None
    lag_task = None
    try:
        db_pool = await asyncpg.create_pool(config.database_url)
        s3_client = boto3.client(
            "s3",
            endpoint_url=config.minio_endpoint,
            aws_access_key_id=config.minio_access_key,
            aws_secret_access_key=config.minio_secret_key,
        )
        broker = KafkaBroker(
            KafkaConfig(
                brokers=config.kafka_brokers,
                topic_prefix=config.kafka_topic_prefix,
                max_retries=config.kafka_max_retries,
            ),
            service_name="ml-scorer",
        )
        consumer = await broker.create_consumer([INPUT_TOPIC], CONSUMER_GROUP)
        lag_task = asyncio.create_task(start_lag_poller(consumer, CONSUMER_GROUP))
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
            broker,
            consumer=consumer,
            shap_explainer=shap_explainer,
            comparables_finder=comparables_finder,
        )
        return 0
    finally:
        if lag_task is not None:
            lag_task.cancel()
            await asyncio.gather(lag_task, return_exceptions=True)
        if broker is not None:
            await broker.stop()
        if db_pool is not None:
            await db_pool.close()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
