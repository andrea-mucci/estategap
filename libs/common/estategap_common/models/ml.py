"""Machine-learning model registry schemas."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import Field

from ._base import EstateGapModel


class ModelStatus(str, Enum):
    STAGING = "staging"
    ACTIVE = "active"
    RETIRED = "retired"


class MlModelVersion(EstateGapModel):
    id: UUID
    country_code: str
    algorithm: str = "lightgbm"
    version_tag: str
    artifact_path: str
    dataset_ref: str | None = None
    feature_names: list[str] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict)
    status: ModelStatus = ModelStatus.STAGING
    transfer_learned: bool = False
    base_country: str | None = None
    confidence: str = "full"
    trained_at: datetime
    promoted_at: datetime | None = None
    retired_at: datetime | None = None
    created_at: datetime
