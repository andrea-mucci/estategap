"""Spatial index validation for listings."""

from __future__ import annotations

from .conftest import collect_plan_values


def test_spatial_index_usage(explain_json, listing_factory) -> None:
    listing_factory()

    plan = explain_json(
        """
        SELECT id
        FROM listings
        WHERE location IS NOT NULL
          AND ST_DWithin(location, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326), 0.1)
        """,
        {"lon": -3.7038, "lat": 40.4168},
        disable_seqscan=True,
    )

    index_names = collect_plan_values(plan, "Index Name")
    node_types = collect_plan_values(plan, "Node Type")
    assert "listings_location_gist_idx" in index_names
    assert {"Index Scan", "Bitmap Index Scan"} & node_types
