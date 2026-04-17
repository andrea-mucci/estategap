"""Environment-backed settings for spider workers."""

from __future__ import annotations

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from estategap_common.s3client import S3Config


class Config(BaseSettings):
    """Environment-backed service configuration."""

    kafka_brokers: str = "localhost:9092"
    kafka_topic_prefix: str = "estategap."
    kafka_max_retries: int = 3
    redis_url: str = "redis://localhost:6379/0"
    estategap_test_mode: bool = Field(default=False, alias="ESTATEGAP_TEST_MODE")
    fixture_s3_bucket: str = Field(default="fixtures", alias="FIXTURE_S3_BUCKET")
    s3_endpoint: str = Field(default="http://localhost:4566", alias="S3_ENDPOINT")
    s3_region: str = Field(default="us-east-1", alias="S3_REGION")
    s3_access_key_id: str = Field(default="test", alias="S3_ACCESS_KEY_ID")
    s3_secret_access_key: str = Field(default="test", alias="S3_SECRET_ACCESS_KEY")
    s3_bucket_prefix: str = Field(default="estategap", alias="S3_BUCKET_PREFIX")
    proxy_manager_addr: str = "localhost:50051"
    proxy_us_url: str = ""
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
    request_timeout_seconds: float = 30.0
    transient_retry_delay_seconds: float = 5.0
    user_agent_seed: int | None = Field(default=None)
    zillow_rate_limit_seconds: float = 3.0
    redfin_rate_limit_seconds: float = 2.0
    realtor_rate_limit_seconds: float = 1.5

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
        if self.kafka_max_retries < 1:
            self.kafka_max_retries = 3
        if self.request_timeout_seconds <= 0:
            self.request_timeout_seconds = 30.0
        if self.transient_retry_delay_seconds <= 0:
            self.transient_retry_delay_seconds = 5.0
        if self.zillow_rate_limit_seconds <= 0:
            self.zillow_rate_limit_seconds = 3.0
        if self.redfin_rate_limit_seconds <= 0:
            self.redfin_rate_limit_seconds = 2.0
        if self.realtor_rate_limit_seconds <= 0:
            self.realtor_rate_limit_seconds = 1.5
        return self

    def to_s3_config(self) -> S3Config:
        return S3Config(
            s3_endpoint=self.s3_endpoint,
            s3_region=self.s3_region,
            s3_access_key_id=self.s3_access_key_id,
            s3_secret_access_key=self.s3_secret_access_key,
            s3_bucket_prefix=self.s3_bucket_prefix,
        )


__all__ = ["Config"]
