"""Shared Pydantic base model configuration."""

from pydantic import BaseModel, ConfigDict


class EstateGapModel(BaseModel):
    """Base model for shared schema types."""

    model_config = ConfigDict(extra="forbid")
