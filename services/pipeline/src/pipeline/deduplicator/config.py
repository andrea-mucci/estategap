"""Runtime settings for the deduplicator worker."""

from __future__ import annotations

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class DeduplicatorSettings(BaseSettings):
    """Environment-backed configuration for the deduplicator service."""

    database_url: str = Field(validation_alias="DATABASE_URL")
    nats_url: str = Field(validation_alias="NATS_URL")
    proximity_meters: int = Field(default=50, validation_alias="DEDUPLICATOR_PROXIMITY_METERS")
    area_tolerance: float = Field(default=0.10, validation_alias="DEDUPLICATOR_AREA_TOLERANCE")
    address_threshold: int = Field(default=85, validation_alias="DEDUPLICATOR_ADDRESS_THRESHOLD")
    metrics_port: int = Field(default=9102, validation_alias="DEDUPLICATOR_METRICS_PORT")
    log_level: str = Field(default="INFO", validation_alias="DEDUPLICATOR_LOG_LEVEL")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @model_validator(mode="after")
    def _validate_values(self) -> "DeduplicatorSettings":
        if self.proximity_meters < 1:
            self.proximity_meters = 50
        if self.area_tolerance <= 0:
            self.area_tolerance = 0.10
        if self.address_threshold < 1:
            self.address_threshold = 85
        if self.metrics_port < 1:
            self.metrics_port = 9102
        return self


__all__ = ["DeduplicatorSettings"]
