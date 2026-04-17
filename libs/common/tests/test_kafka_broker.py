from __future__ import annotations

import asyncio

import pytest

pytest.importorskip("aiokafka")
pytest.importorskip("testcontainers.kafka")

from estategap_common.broker import KafkaBroker, KafkaConfig, Message
from estategap_common.testing.kafka import KafkaTestContainer


@pytest.mark.integration
@pytest.mark.asyncio
async def test_kafka_broker_round_trip() -> None:
    with KafkaTestContainer() as container:
        config = KafkaConfig(brokers=container.get_bootstrap_server(), max_retries=3)
        publisher = KafkaBroker(config, service_name="common-test-publisher")
        consumer_broker = KafkaBroker(config, service_name="common-test-consumer")

        received: asyncio.Queue[Message] = asyncio.Queue(maxsize=1)

        async def handler(message: Message) -> None:
            await received.put(message)

        consume_task = asyncio.create_task(
            consumer_broker.subscribe(["raw-listings"], "common-roundtrip", handler)
        )

        try:
            await publisher.publish("raw-listings", "ES", b'{"listing_id":"abc"}')
            message = await asyncio.wait_for(received.get(), timeout=30)
            assert message.key == "ES"
            assert message.value == b'{"listing_id":"abc"}'
            assert message.topic == "estategap.raw-listings"
        finally:
            consume_task.cancel()
            await asyncio.gather(consume_task, return_exceptions=True)
            await publisher.stop()
            await consumer_broker.stop()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_kafka_broker_dead_letters_after_retries() -> None:
    with KafkaTestContainer() as container:
        config = KafkaConfig(brokers=container.get_bootstrap_server(), max_retries=3)
        publisher = KafkaBroker(config, service_name="common-test-publisher")
        failing_broker = KafkaBroker(config, service_name="common-test-failer")
        dlt_broker = KafkaBroker(config, service_name="common-test-dlt")

        attempts = 0
        dead_letters: asyncio.Queue[Message] = asyncio.Queue(maxsize=1)

        async def failing_handler(_: Message) -> None:
            nonlocal attempts
            attempts += 1
            raise RuntimeError("simulated failure")

        async def dlt_handler(message: Message) -> None:
            await dead_letters.put(message)

        source_task = asyncio.create_task(
            failing_broker.subscribe(["raw-listings"], "common-dead-letter-source", failing_handler)
        )
        dlt_task = asyncio.create_task(
            dlt_broker.subscribe(["dead-letter"], "common-dead-letter-sink", dlt_handler)
        )

        try:
            await publisher.publish("raw-listings", "FR", b'{"listing_id":"boom"}')
            dead_letter = await asyncio.wait_for(dead_letters.get(), timeout=45)
            assert attempts == 3
            assert dead_letter.key == "FR"
            assert dead_letter.headers["x-original-topic"] == "estategap.raw-listings"
            assert dead_letter.headers["x-retry-count"] == "3"
            assert dead_letter.headers["x-service"] == "common-test-failer"
        finally:
            source_task.cancel()
            dlt_task.cancel()
            await asyncio.gather(source_task, dlt_task, return_exceptions=True)
            await publisher.stop()
            await failing_broker.stop()
            await dlt_broker.stop()
