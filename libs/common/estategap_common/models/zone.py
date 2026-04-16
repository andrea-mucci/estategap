"""Zone Pydantic model."""

from pydantic import BaseModel


class Zone(BaseModel):
    id: str
    name: str
    country_code: str
    geometry_wkt: str
    parent_zone_id: str | None = None
