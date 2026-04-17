"""Runtime settings for the enrichment worker."""

from __future__ import annotations

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class EnricherSettings(BaseSettings):
    """Environment-backed configuration for the enricher service."""

    database_url: str = Field(validation_alias="DATABASE_URL")
    nats_url: str = Field(validation_alias="NATS_URL")
    catastro_rate_limit: float = Field(
        default=1.0,
        validation_alias="ENRICHER_CATASTRO_RATE_LIMIT",
    )
    overpass_url: str = Field(
        default="https://overpass-api.de/api/interpreter",
        validation_alias="ENRICHER_OVERPASS_URL",
    )
    overpass_cache_ttl: int = Field(
        default=300,
        validation_alias="ENRICHER_OVERPASS_CACHE_TTL",
    )
    metrics_port: int = Field(default=9103, validation_alias="ENRICHER_METRICS_PORT")
    log_level: str = Field(default="INFO", validation_alias="ENRICHER_LOG_LEVEL")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @model_validator(mode="after")
    def _validate_values(self) -> "EnricherSettings":
        if self.catastro_rate_limit <= 0:
            self.catastro_rate_limit = 1.0
        if self.overpass_cache_ttl < 1:
            self.overpass_cache_ttl = 300
        if self.metrics_port < 1:
            self.metrics_port = 9103
        return self


__all__ = ["EnricherSettings"]
