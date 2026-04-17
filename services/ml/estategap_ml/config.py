"""Configuration for the ML trainer service."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    """Typed environment-backed settings for the training pipeline."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    database_url: str = Field(alias="DATABASE_URL")
    mlflow_tracking_uri: str = Field(alias="MLFLOW_TRACKING_URI")
    nats_url: str = Field(alias="NATS_URL")
    minio_endpoint: str = Field(alias="MINIO_ENDPOINT")
    minio_access_key: str = Field(alias="MINIO_ACCESS_KEY")
    minio_secret_key: str = Field(alias="MINIO_SECRET_KEY")
    minio_bucket: str = Field(default="estategap-models", alias="MINIO_BUCKET")
    promotion_mape_improvement_pct: float = Field(
        default=0.02,
        alias="PROMOTION_MAPE_IMPROVEMENT_PCT",
    )
    min_listings_per_country: int = Field(default=5000, alias="MIN_LISTINGS_PER_COUNTRY")
    optuna_n_trials: int = Field(default=50, alias="OPTUNA_N_TRIALS")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    prometheus_pushgateway_url: str | None = Field(
        default=None,
        alias="PROMETHEUS_PUSHGATEWAY_URL",
    )
    local_artifact_dir: Path = Field(default=Path("./artifacts"), alias="LOCAL_ARTIFACT_DIR")

