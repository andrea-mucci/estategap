"""ScoringResult and ShapValue Pydantic models."""

from datetime import datetime

from pydantic import BaseModel


class ShapValue(BaseModel):
    feature_name: str
    value: float


class ScoringResult(BaseModel):
    listing_id: str
    deal_score: float
    shap_values: list[ShapValue]
    model_version: str
    country_code: str
    scored_at: datetime
