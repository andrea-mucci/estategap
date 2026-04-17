"""Configuration for the ML services."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from estategap_common.s3client import S3Config


class Config(BaseSettings):
    """Typed environment-backed settings for the ML trainer and scorer."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    database_url: str = Field(alias="DATABASE_URL")
    mlflow_tracking_uri: str = Field(alias="MLFLOW_TRACKING_URI")
    kafka_brokers: str = Field(default="localhost:9092", alias="KAFKA_BROKERS")
    kafka_topic_prefix: str = Field(default="estategap.", alias="KAFKA_TOPIC_PREFIX")
    kafka_max_retries: int = Field(default=3, alias="KAFKA_MAX_RETRIES")
    s3_endpoint: str = Field(alias="S3_ENDPOINT")
    s3_region: str = Field(default="fsn1", alias="S3_REGION")
    s3_access_key_id: str = Field(alias="S3_ACCESS_KEY_ID")
    s3_secret_access_key: str = Field(alias="S3_SECRET_ACCESS_KEY")
    s3_bucket_prefix: str = Field(alias="S3_BUCKET_PREFIX")
    promotion_mape_improvement_pct: float = Field(
        default=0.02,
        alias="PROMOTION_MAPE_IMPROVEMENT_PCT",
    )
    min_listings_per_country: int = Field(default=5000, alias="MIN_LISTINGS_PER_COUNTRY")
    transfer_min_listings: int = Field(default=5000, alias="ML_TRANSFER_MIN_LISTINGS")
    transfer_mape_max: float = Field(default=0.20, alias="ML_TRANSFER_MAPE_MAX")
    transfer_base_country: str = Field(default="ES", alias="ML_TRANSFER_BASE_COUNTRY")
    optuna_n_trials: int = Field(default=50, alias="OPTUNA_N_TRIALS")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    prometheus_pushgateway_url: str | None = Field(
        default=None,
        alias="PROMETHEUS_PUSHGATEWAY_URL",
    )
    grpc_port: int = Field(default=50051, alias="GRPC_PORT")
    scorer_batch_size: int = Field(default=50, alias="SCORER_BATCH_SIZE")
    scorer_batch_flush_seconds: int = Field(default=5, alias="SCORER_BATCH_FLUSH_SECONDS")
    model_poll_interval_seconds: int = Field(default=60, alias="MODEL_POLL_INTERVAL_SECONDS")
    comparables_refresh_interval_seconds: int = Field(
        default=3600,
        alias="COMPARABLES_REFRESH_INTERVAL_SECONDS",
    )
    shap_timeout_seconds: float = Field(default=2.0, alias="SHAP_TIMEOUT_SECONDS")
    prometheus_port: int = Field(default=9091, alias="PROMETHEUS_PORT")
    local_artifact_dir: Path = Field(default=Path("./artifacts"), alias="LOCAL_ARTIFACT_DIR")

    @model_validator(mode="after")
    def _validate_kafka(self) -> "Config":
        if self.kafka_max_retries < 1:
            self.kafka_max_retries = 3
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
