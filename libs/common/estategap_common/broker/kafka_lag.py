"""Prometheus lag metrics for Kafka consumers."""

from __future__ import annotations

import asyncio
from typing import Any

from prometheus_client import Gauge


kafka_consumer_lag = Gauge(
    "estategap_kafka_consumer_lag",
    "Kafka consumer group lag per topic partition.",
    ["group", "topic", "partition"],
)


async def start_lag_poller(consumer: Any, group: str) -> None:
    """Continuously export lag for the consumer's assigned topic partitions."""

    while True:
        assignments = list(consumer.assignment())
        if assignments:
            end_offsets = await consumer.end_offsets(assignments)
            for partition in assignments:
                try:
                    position = await consumer.position(partition)
                except Exception:  # noqa: BLE001
                    continue

                lag = max(end_offsets.get(partition, 0) - position, 0)
                kafka_consumer_lag.labels(
                    group=group,
                    topic=partition.topic,
                    partition=str(partition.partition),
                ).set(float(lag))

        await asyncio.sleep(30)


__all__ = ["kafka_consumer_lag", "start_lag_poller"]
