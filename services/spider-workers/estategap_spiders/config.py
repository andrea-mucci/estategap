"""Runtime configuration for spider workers."""

from __future__ import annotations

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    """Environment-backed service configuration."""

    nats_url: str = "nats://localhost:4222"
    redis_url: str = "redis://localhost:6379/0"
    proxy_manager_addr: str = "localhost:50051"
    metrics_port: int = 9102
    log_level: str = "INFO"
    idealista_api_token: str = ""
    idealista_it_api_token: str = ""
    immobiliare_api_token: str = ""
    request_min_delay: float = 2.0
    request_max_delay: float = 5.0
    max_concurrent_per_portal: int = 3
    session_rotation_every: int = 10
    quarantine_ttl_days: int = 30
    consumer_stream: str = "SCRAPER_COMMANDS"
    consumer_subject: str = "scraper.commands.>"
    consumer_durable: str = "spider-worker"
    request_timeout_seconds: float = 30.0
    transient_retry_delay_seconds: float = 5.0
    user_agent_seed: int | None = Field(default=None)

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @model_validator(mode="after")
    def _validate_delays(self) -> "Config":
        if self.request_min_delay < 0:
            self.request_min_delay = 0.0
        if self.request_max_delay < self.request_min_delay:
            self.request_max_delay = self.request_min_delay
        if self.max_concurrent_per_portal < 1:
            self.max_concurrent_per_portal = 1
        if self.session_rotation_every < 1:
            self.session_rotation_every = 1
        if self.quarantine_ttl_days < 1:
            self.quarantine_ttl_days = 1
        if self.request_timeout_seconds <= 0:
            self.request_timeout_seconds = 30.0
        if self.transient_retry_delay_seconds <= 0:
            self.transient_retry_delay_seconds = 5.0
        return self
