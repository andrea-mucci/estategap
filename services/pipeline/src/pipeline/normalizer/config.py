"""Runtime settings for the normalizer worker."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class NormalizerSettings(BaseSettings):
    """Environment-backed configuration for the normalizer service."""

    database_url: str = Field(validation_alias="DATABASE_URL")
    nats_url: str = Field(validation_alias="NATS_URL")
    batch_size: int = Field(default=50, validation_alias="NORMALIZER_BATCH_SIZE")
    batch_timeout: float = Field(default=1.0, validation_alias="NORMALIZER_BATCH_TIMEOUT")
    mappings_dir: Path = Field(
        default=Path("config/mappings"),
        validation_alias="NORMALIZER_MAPPINGS_DIR",
    )
    metrics_port: int = Field(default=9101, validation_alias="NORMALIZER_METRICS_PORT")
    log_level: str = Field(default="INFO", validation_alias="NORMALIZER_LOG_LEVEL")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @model_validator(mode="after")
    def _validate_values(self) -> "NormalizerSettings":
        if self.batch_size < 1:
            self.batch_size = 1
        if self.batch_timeout <= 0:
            self.batch_timeout = 1.0
        if self.metrics_port < 1:
            self.metrics_port = 9101
        return self


__all__ = ["NormalizerSettings"]
