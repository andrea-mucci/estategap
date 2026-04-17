"""Configuration for the AI chat service."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, cast

from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    class BaseSettings(BaseModel):
        model_config: ClassVar[ConfigDict]

    def SettingsConfigDict(**kwargs: object) -> ConfigDict:
        return cast(ConfigDict, dict(kwargs))
else:
    try:
        from pydantic_settings import BaseSettings, SettingsConfigDict
    except ModuleNotFoundError:  # pragma: no cover - fallback for constrained local envs
        BaseSettings = BaseModel

        def SettingsConfigDict(**kwargs: object) -> ConfigDict:
            return cast(ConfigDict, dict(kwargs))


class Config(BaseSettings):
    """Typed environment-backed settings for the AI chat service."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    grpc_port: int = Field(default=50053, alias="GRPC_PORT")
    metrics_port: int = Field(default=9090, alias="METRICS_PORT")
    llm_provider: str = Field(default="claude", alias="LLM_PROVIDER")
    fallback_llm_provider: str = Field(default="openai", alias="FALLBACK_LLM_PROVIDER")
    anthropic_api_key: str | None = Field(default=None, alias="ANTHROPIC_API_KEY")
    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    litellm_model: str | None = Field(default=None, alias="LITELLM_MODEL")
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")
    database_url: str = Field(alias="DATABASE_URL")
    api_gateway_grpc_addr: str = Field(
        default="localhost:50051",
        alias="API_GATEWAY_GRPC_ADDR",
    )
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
