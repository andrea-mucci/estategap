"""Configuration for the ML services."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


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
    minio_endpoint: str = Field(alias="MINIO_ENDPOINT")
    minio_access_key: str = Field(alias="MINIO_ACCESS_KEY")
    minio_secret_key: str = Field(alias="MINIO_SECRET_KEY")
    minio_bucket: str = Field(default="ml-models", alias="MINIO_BUCKET")
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


__all__ = ["Config"]
