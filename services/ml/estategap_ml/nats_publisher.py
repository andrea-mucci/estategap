"""NATS event publisher helpers for ML training events."""

from __future__ import annotations

from datetime import UTC, datetime

from estategap_common.nats_client import NatsClient
from pydantic import BaseModel, ConfigDict, Field


class TrainingCompletedEvent(BaseModel):
    """Payload for `ml.training.completed`."""

    model_config = ConfigDict(extra="ignore")

    country_code: str
    model_version_tag: str
    mape_national: float
    promoted: bool
    previous_champion_tag: str | None = None
    artifact_path: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))


class TrainingFailedEvent(BaseModel):
    """Payload for `ml.training.failed`."""

    model_config = ConfigDict(extra="ignore")

    country_code: str | None = None
    error: str
    stage: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))


async def _publish(subject: str, payload: BaseModel, nats_url: str) -> None:
    client = NatsClient()
    await client.connect(nats_url)
    try:
        await client.publish(subject, payload.model_dump_json().encode("utf-8"))
    finally:
        await client.close()


async def publish_completed(event: TrainingCompletedEvent, nats_url: str) -> None:
    """Publish a completed event onto the ML events stream."""

    await _publish("ml.training.completed", event, nats_url)


async def publish_failed(event: TrainingFailedEvent, nats_url: str) -> None:
    """Publish a failed event onto the ML events stream."""

    await _publish("ml.training.failed", event, nats_url)
