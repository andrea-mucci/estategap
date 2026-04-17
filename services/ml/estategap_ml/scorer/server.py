"""Scorer gRPC server lifecycle."""

from __future__ import annotations

import asyncio
from typing import Any

import grpc
from estategap_common.broker import KafkaBroker

from estategap.v1 import ml_scoring_pb2_grpc

from .comparables import ComparablesFinder
from .kafka_consumer import KafkaConsumer
from .model_registry import ModelRegistry
from .servicer import MLScoringServicer
from .shap_explainer import ShapExplainer


async def serve(
    config: Any,
    registry: ModelRegistry,
    db_pool: Any,
    broker: KafkaBroker,
    *,
    consumer: Any | None = None,
    shap_explainer: ShapExplainer | None = None,
    comparables_finder: ComparablesFinder | None = None,
) -> None:
    """Run the scorer gRPC server plus background tasks."""

    server = grpc.aio.server()
    ml_scoring_pb2_grpc.add_MLScoringServiceServicer_to_server(
        MLScoringServicer(
            config=config,
            db_pool=db_pool,
            registry=registry,
            broker=broker,
            shap_explainer=shap_explainer,
            comparables_finder=comparables_finder,
        ),
        server,
    )
    server.add_insecure_port(f"[::]:{config.grpc_port}")
    scorer_consumer = KafkaConsumer(
        config=config,
        db_pool=db_pool,
        registry=registry,
        broker=broker,
        consumer=consumer,
        shap_explainer=shap_explainer,
        comparables_finder=comparables_finder,
    )
    await server.start()
    tasks = [
        asyncio.create_task(registry.poll_loop(db_pool), name="scorer-model-poll"),
        asyncio.create_task(scorer_consumer.consume_loop(), name="scorer-kafka-consumer"),
    ]
    if comparables_finder is not None:
        tasks.append(asyncio.create_task(comparables_finder.refresh_loop(db_pool), name="scorer-comparables-refresh"))
    try:
        await server.wait_for_termination()
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await server.stop(grace=5)


__all__ = ["serve"]
