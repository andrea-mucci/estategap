from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import pytest
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from estategap_common.testing.kafka import KafkaTestContainer

from estategap_common.models.listing import RawListing
from estategap_spiders.consumer import run
from estategap_spiders.models import ScraperCommand

pytest.importorskip("testcontainers.kafka")


@pytest.mark.asyncio
async def test_kafka_consumer_round_trip(spider_config) -> None:
    with KafkaTestContainer() as container:
        bootstrap = container.get_bootstrap_server()
        config = spider_config.model_copy(update={"kafka_brokers": bootstrap})

        subscriber = AIOKafkaConsumer(
            "estategap.raw-listings",
            bootstrap_servers=bootstrap,
            group_id="spider-test-roundtrip",
            enable_auto_commit=False,
            auto_offset_reset="earliest",
        )
        publisher = AIOKafkaProducer(bootstrap_servers=bootstrap)
        await subscriber.start()
        await publisher.start()

        consumer_task = asyncio.create_task(run(config))
        try:
            await asyncio.sleep(1)

            command = ScraperCommand(
                job_id="job-1",
                portal="fixture",
                country="ES",
                mode="full",
                zone_filter=["madrid-centro"],
                search_url="https://example.com/search",
                created_at=datetime.now(UTC),
            )
            await publisher.send_and_wait(
                "estategap.scraper-commands",
                key=b"ES.fixture",
                value=command.model_dump_json().encode(),
            )

            message = await _next_record(subscriber)
            listing = RawListing.model_validate_json(message.value)
            assert listing.portal == "fixture"
            assert listing.country_code == "ES"
        finally:
            consumer_task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await consumer_task
            await subscriber.stop()
            await publisher.stop()


async def _next_record(consumer: AIOKafkaConsumer) -> object:
    deadline = asyncio.get_running_loop().time() + 10
    while asyncio.get_running_loop().time() < deadline:
        records = await consumer.getmany(timeout_ms=1000)
        for partition_records in records.values():
            if partition_records:
                return partition_records[0]
    raise AssertionError("timed out waiting for Kafka record")
