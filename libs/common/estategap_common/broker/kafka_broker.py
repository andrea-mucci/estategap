"""Kafka-backed broker implementation for Python services."""

from __future__ import annotations

import ssl
from collections.abc import Iterable
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, cast

import structlog
from pydantic_settings import BaseSettings, SettingsConfigDict

from .types import Message, MessageHandler


if TYPE_CHECKING:
    from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
    from aiokafka.structs import ConsumerRecord
else:  # pragma: no cover - runtime imports are performed lazily.
    AIOKafkaConsumer = Any
    AIOKafkaProducer = Any
    ConsumerRecord = Any


LOGGER = structlog.get_logger(__name__)
DEFAULT_TOPIC_PREFIX = "estategap."
DEAD_LETTER_TOPIC = "dead-letter"
ERROR_HEADER_LIMIT = 512


class KafkaConfig(BaseSettings):
    """Environment-backed Kafka settings shared across services."""

    brokers: str = "localhost:9092"
    topic_prefix: str = DEFAULT_TOPIC_PREFIX
    max_retries: int = 3
    tls_enabled: bool = False
    sasl_username: str = ""
    sasl_password: str = ""

    model_config = SettingsConfigDict(env_prefix="KAFKA_", extra="ignore")

    @property
    def broker_list(self) -> list[str]:
        return [broker.strip() for broker in self.brokers.split(",") if broker.strip()]

    @property
    def normalized_topic_prefix(self) -> str:
        prefix = self.topic_prefix.strip() or DEFAULT_TOPIC_PREFIX
        return prefix if prefix.endswith(".") else f"{prefix}."

    @property
    def retry_limit(self) -> int:
        return self.max_retries if self.max_retries > 0 else 3


class KafkaBroker:
    """Thin wrapper around aiokafka producer/consumer primitives."""

    def __init__(self, config: KafkaConfig, *, service_name: str = "unknown-service") -> None:
        self._config = config
        self._service_name = service_name.strip() or "unknown-service"
        self._producer: AIOKafkaProducer | None = None
        self._consumers: dict[str, AIOKafkaConsumer] = {}

    async def start(self) -> None:
        """Start the shared Kafka producer lazily."""

        if self._producer is not None:
            return

        from aiokafka import AIOKafkaProducer

        producer = AIOKafkaProducer(
            bootstrap_servers=self._config.broker_list,
            **self._client_options(),
        )
        await producer.start()
        self._producer = cast("AIOKafkaProducer", producer)

    async def stop(self) -> None:
        """Stop all managed Kafka clients."""

        for group, consumer in list(self._consumers.items()):
            await consumer.stop()
            self._consumers.pop(group, None)

        if self._producer is not None:
            await self._producer.stop()
            self._producer = None

    async def publish(self, topic: str, key: str, value: bytes) -> None:
        """Publish a message without custom headers."""

        await self.publish_with_headers(topic, key, value, {})

    async def publish_with_headers(
        self,
        topic: str,
        key: str,
        value: bytes,
        headers: dict[str, str],
    ) -> None:
        """Publish a message with string headers."""

        await self.start()
        producer = self._require_producer()
        await producer.send_and_wait(
            self.full_topic_name(topic),
            value=value,
            key=key.encode("utf-8"),
            headers=[(header_key, header_value.encode("utf-8")) for header_key, header_value in headers.items()],
        )

    async def create_consumer(self, topics: str | Iterable[str], group: str) -> AIOKafkaConsumer:
        """Create and start a managed consumer for one or more topics."""

        from aiokafka import AIOKafkaConsumer

        topic_list = [topic for topic in _as_topic_list(topics) if topic.strip()]
        if not topic_list:
            msg = "Kafka consumer requires at least one topic"
            raise ValueError(msg)
        if not group.strip():
            msg = "Kafka consumer requires a consumer group"
            raise ValueError(msg)

        consumer = AIOKafkaConsumer(
            *(self.full_topic_name(topic) for topic in topic_list),
            bootstrap_servers=self._config.broker_list,
            group_id=group.strip(),
            enable_auto_commit=False,
            auto_offset_reset="latest",
            max_partition_fetch_bytes=10 * 1024 * 1024,
            **self._client_options(),
        )
        await consumer.start()
        self._consumers[group] = cast("AIOKafkaConsumer", consumer)
        return cast("AIOKafkaConsumer", consumer)

    def get_consumer(self, group: str) -> AIOKafkaConsumer | None:
        """Return the managed consumer for a group, if it has been created."""

        return self._consumers.get(group)

    async def consume(self, consumer: AIOKafkaConsumer, group: str, handler: MessageHandler) -> None:
        """Run the message loop for a started consumer."""

        async for record in consumer:
            message = self._to_message(record)
            for attempt in range(1, self._config.retry_limit + 1):
                try:
                    await handler(message)
                except Exception as exc:  # noqa: BLE001
                    if attempt == self._config.retry_limit:
                        await self._handle_failure(record, exc, attempt, group)
                        await consumer.commit()
                    continue

                await consumer.commit()
                break

    async def subscribe(self, topics: str | Iterable[str], group: str, handler: MessageHandler) -> None:
        """Create a consumer, run the loop, and clean up when it exits."""

        consumer = await self.create_consumer(topics, group)
        try:
            await self.consume(consumer, group, handler)
        finally:
            await consumer.stop()
            self._consumers.pop(group, None)

    def full_topic_name(self, topic: str) -> str:
        """Return the configured fully-qualified Kafka topic name."""

        trimmed = topic.strip()
        if trimmed.startswith(self._config.normalized_topic_prefix):
            return trimmed
        return f"{self._config.normalized_topic_prefix}{trimmed}"

    def _client_options(self) -> dict[str, object]:
        options: dict[str, object] = {}
        has_sasl = bool(self._config.sasl_username or self._config.sasl_password)
        if self._config.tls_enabled:
            options["ssl_context"] = ssl.create_default_context()
        if has_sasl:
            options["sasl_mechanism"] = "PLAIN"
            options["sasl_plain_username"] = self._config.sasl_username
            options["sasl_plain_password"] = self._config.sasl_password

        if self._config.tls_enabled and has_sasl:
            options["security_protocol"] = "SASL_SSL"
        elif self._config.tls_enabled:
            options["security_protocol"] = "SSL"
        elif has_sasl:
            options["security_protocol"] = "SASL_PLAINTEXT"

        return options

    async def _handle_failure(
        self,
        record: ConsumerRecord,
        error: Exception,
        retry_count: int,
        group: str,
    ) -> None:
        headers = {key: value for key, value in self._decode_headers(record.headers).items()}
        headers.update(
            {
                "x-original-topic": record.topic,
                "x-error": _truncate(str(error), ERROR_HEADER_LIMIT),
                "x-retry-count": str(retry_count),
                "x-timestamp": datetime.now(tz=UTC).isoformat(),
                "x-service": self._service_name or group,
            }
        )
        LOGGER.warning(
            "broker_dead_lettered_message",
            topic=record.topic,
            group=group,
            retry_count=retry_count,
            error=str(error),
        )
        await self.publish_with_headers(
            DEAD_LETTER_TOPIC,
            _decode_key(record.key),
            bytes(record.value),
            headers,
        )

    def _require_producer(self) -> AIOKafkaProducer:
        if self._producer is None:  # pragma: no cover - guarded by start()
            msg = "Kafka producer has not been started"
            raise RuntimeError(msg)
        return self._producer

    def _to_message(self, record: ConsumerRecord) -> Message:
        return Message(
            key=_decode_key(record.key),
            value=bytes(record.value),
            topic=record.topic,
            headers=self._decode_headers(record.headers),
        )

    @staticmethod
    def _decode_headers(headers: Any) -> dict[str, str]:
        decoded: dict[str, str] = {}
        for key, value in headers or []:
            decoded[str(key)] = value.decode("utf-8") if isinstance(value, (bytes, bytearray)) else str(value)
        return decoded


def _decode_key(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (bytes, bytearray)):
        return value.decode("utf-8")
    return str(value)


def _truncate(value: str, limit: int) -> str:
    return value if limit <= 0 or len(value) <= limit else value[:limit]


def _as_topic_list(topics: str | Iterable[str]) -> list[str]:
    if isinstance(topics, str):
        return [topics]
    return list(topics)


__all__ = ["KafkaBroker", "KafkaConfig"]
