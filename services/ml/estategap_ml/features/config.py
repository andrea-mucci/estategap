"""Country-specific ML feature configuration models."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field


class EncodingRule(BaseModel):
    """Declarative encoding rule for one categorical feature."""

    categories: list[str] = Field(default_factory=list)
    strategy: Literal["onehot", "label", "ordinal"]


class CountryFeatureConfig(BaseModel):
    """A single country's feature configuration."""

    country: str
    description: str
    base_features: list[str] = Field(default_factory=list)
    country_specific_features: list[str] = Field(default_factory=list)
    optional_features: list[str] = Field(default_factory=list)
    encoding_rules: dict[str, EncodingRule] = Field(default_factory=dict)
    feature_drops: list[str] = Field(default_factory=list)

    @property
    def all_features(self) -> list[str]:
        features = [*self.base_features, *self.country_specific_features]
        return [feature for feature in features if feature not in set(self.feature_drops)]

    @classmethod
    def from_yaml(cls, path: Path) -> "CountryFeatureConfig":
        if not path.exists():
            msg = f"Feature configuration file not found: {path}"
            raise FileNotFoundError(msg)
        with path.open("r", encoding="utf-8") as handle:
            payload = yaml.safe_load(handle) or {}
        return cls.model_validate(payload)


__all__ = ["CountryFeatureConfig", "EncodingRule"]
