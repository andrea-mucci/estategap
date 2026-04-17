"""Kafka testcontainer helpers shared by Python services."""

from __future__ import annotations

from typing import Any


class KafkaTestContainer:
    """Thin wrapper around testcontainers' KafkaContainer."""

    def __init__(self, image: str = "confluentinc/cp-kafka:7.6.1") -> None:
        from testcontainers.kafka import KafkaContainer

        self._container = KafkaContainer(image)

    def __enter__(self) -> "KafkaTestContainer":
        self.start()
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self.stop()

    def start(self) -> "KafkaTestContainer":
        self._container.start()
        return self

    def stop(self) -> None:
        self._container.stop()

    def get_bootstrap_server(self) -> str:
        return str(self._container.get_bootstrap_server())


__all__ = ["KafkaTestContainer"]
