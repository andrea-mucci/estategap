"""Runtime settings for the change-detector worker."""

from __future__ import annotations

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class ChangeDetectorSettings(BaseSettings):
    """Environment-backed configuration for the change detector service."""

    database_url: str = Field(validation_alias="DATABASE_URL")
    nats_url: str = Field(validation_alias="NATS_URL")
    cycle_window_hours: int = Field(default=6, validation_alias="CHANGE_DETECTOR_CYCLE_WINDOW_HOURS")
    fallback_interval_h: int = Field(
        default=12,
        validation_alias="CHANGE_DETECTOR_FALLBACK_INTERVAL_H",
    )
    metrics_port: int = Field(default=9104, validation_alias="CHANGE_DETECTOR_METRICS_PORT")
    log_level: str = Field(default="INFO", validation_alias="CHANGE_DETECTOR_LOG_LEVEL")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @model_validator(mode="after")
    def _validate_values(self) -> "ChangeDetectorSettings":
        if self.cycle_window_hours < 1:
            self.cycle_window_hours = 6
        if self.fallback_interval_h < 1:
            self.fallback_interval_h = 12
        if self.metrics_port < 1:
            self.metrics_port = 9104
        return self


__all__ = ["ChangeDetectorSettings"]
