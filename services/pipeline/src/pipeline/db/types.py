"""Shared SQLAlchemy/PostGIS type aliases used by schema models."""

from __future__ import annotations

from geoalchemy2 import Geometry
from sqlalchemy.dialects.postgresql import JSONB as PostgresJSONB

GeometryPoint = Geometry(geometry_type="POINT", srid=4326)
GeometryMultiPolygon = Geometry(geometry_type="MULTIPOLYGON", srid=4326)
JSONB = PostgresJSONB

__all__ = ["GeometryMultiPolygon", "GeometryPoint", "JSONB"]
