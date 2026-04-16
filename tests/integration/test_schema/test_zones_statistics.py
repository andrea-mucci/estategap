"""Zone hierarchy and materialized-view tests."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Engine

from .conftest import collect_plan_values


def test_zone_insert_with_geometry(db_engine: Engine, zone_factory) -> None:
    zone_id = zone_factory(slug="madrid-city")

    with db_engine.connect() as connection:
        geometry = connection.execute(
            text("SELECT ST_AsText(geometry) FROM zones WHERE id = :zone_id"),
            {"zone_id": zone_id},
        ).scalar_one()

    assert geometry.startswith("MULTIPOLYGON")


def test_zone_hierarchy(db_engine: Engine, zone_factory) -> None:
    parent_id = zone_factory(name="Community of Madrid", level=1, slug="community-madrid")
    child_id = zone_factory(name="Madrid", level=3, parent_id=parent_id, slug="madrid-city")

    with db_engine.connect() as connection:
        row = connection.execute(
            text("SELECT parent_id FROM zones WHERE id = :child_id"),
            {"child_id": child_id},
        ).mappings().one()

    assert row["parent_id"] == parent_id


def test_gist_index_on_geometry(explain_json, zone_factory) -> None:
    zone_factory()

    plan = explain_json(
        """
        SELECT id
        FROM zones
        WHERE ST_Contains(geometry, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326))
        """,
        {"lon": -3.7, "lat": 40.4},
        disable_seqscan=True,
    )

    assert "zones_geometry_gist_idx" in collect_plan_values(plan, "Index Name")


def test_zone_statistics_refresh(db_engine: Engine, zone_factory, listing_factory) -> None:
    zone_id = zone_factory(slug="stats-zone")
    listing_factory(zone_id=zone_id, source_id="stats-1", price_per_m2_eur=3000)
    listing_factory(zone_id=zone_id, source_id="stats-2", price_per_m2_eur=3200)
    listing_factory(zone_id=zone_id, source_id="stats-3", price_per_m2_eur=3400)

    with db_engine.begin() as connection:
        connection.execute(text("SELECT refresh_zone_statistics()"))

    with db_engine.connect() as connection:
        row = connection.execute(
            text(
                """
                SELECT listing_count, median_price_m2_eur
                FROM zone_statistics
                WHERE zone_id = :zone_id
                """
            ),
            {"zone_id": zone_id},
        ).mappings().one()

    assert row["listing_count"] == 3
    assert row["median_price_m2_eur"] is not None


def test_empty_zone_excluded(db_engine: Engine, zone_factory) -> None:
    zone_id = zone_factory(slug="empty-zone")

    with db_engine.begin() as connection:
        connection.execute(text("SELECT refresh_zone_statistics()"))

    with db_engine.connect() as connection:
        row = connection.execute(
            text("SELECT zone_id FROM zone_statistics WHERE zone_id = :zone_id"),
            {"zone_id": zone_id},
        ).first()

    assert row is None
