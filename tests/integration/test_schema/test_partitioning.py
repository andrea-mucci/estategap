"""Partition-pruning validation for the listings table."""

from __future__ import annotations

from sqlalchemy.engine import Engine

from .conftest import collect_plan_values


def test_country_partition_pruning(db_engine: Engine, explain_json, listing_factory) -> None:
    countries = ["ES", "FR", "IT", "PT", "DE", "GB", "NL", "US", "JP"]
    for country in countries:
        listing_factory(country=country, source_id=f"{country.lower()}-listing")

    expected_partitions = {
        "ES": "listings_es",
        "FR": "listings_fr",
        "IT": "listings_it",
        "PT": "listings_pt",
        "DE": "listings_de",
        "GB": "listings_gb",
        "NL": "listings_nl",
        "US": "listings_us",
        "JP": "listings_other",
    }

    all_partitions = set(expected_partitions.values())
    for country, expected_partition in expected_partitions.items():
        plan = explain_json(
            "SELECT id FROM listings WHERE country = :country",
            {"country": country},
        )
        relations = collect_plan_values(plan, "Relation Name")
        assert expected_partition in relations
        assert relations <= {expected_partition}
        assert expected_partition in all_partitions
