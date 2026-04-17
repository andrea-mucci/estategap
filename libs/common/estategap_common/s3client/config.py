"""Configuration and error types for the shared Python S3 clients."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class S3Error(Exception):
    """Base exception for all S3 client errors."""


class S3HealthCheckError(S3Error):
    """Raised when one or more required buckets are missing or inaccessible."""

    def __init__(self, missing_buckets: list[str]) -> None:
        self.missing_buckets = missing_buckets
        super().__init__(f"S3 health check failed: missing buckets: {missing_buckets}")


class S3Config(BaseSettings):
    """Shared S3 configuration loaded from environment variables."""

    s3_endpoint: str = Field(alias="S3_ENDPOINT")
    s3_region: str = Field(default="fsn1", alias="S3_REGION")
    s3_access_key_id: str = Field(alias="S3_ACCESS_KEY_ID")
    s3_secret_access_key: str = Field(alias="S3_SECRET_ACCESS_KEY")
    s3_bucket_prefix: str = Field(alias="S3_BUCKET_PREFIX")

    model_config = SettingsConfigDict(populate_by_name=True, case_sensitive=False)


__all__ = ["S3Config", "S3Error", "S3HealthCheckError"]
