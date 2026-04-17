"""Pydantic models for spider worker messages."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, model_validator


class ScraperCommand(BaseModel):
    """Incoming scrape job published by the scrape orchestrator."""

    job_id: str
    portal: str
    country: str
    mode: str
    zone_filter: list[str] = Field(default_factory=list)
    search_url: str
    created_at: datetime

    @model_validator(mode="after")
    def _normalise_fields(self) -> "ScraperCommand":
        self.portal = self.portal.strip().lower()
        self.country = self.country.strip().lower()
        self.mode = self.mode.strip().lower()
        self.zone_filter = [zone.strip() for zone in self.zone_filter if zone.strip()]
        self.search_url = self.search_url.strip()
        return self
