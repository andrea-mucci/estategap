from __future__ import annotations

import json

from estategap_spiders.spiders.us_zillow_parser import parse_listing_detail, parse_search_results
from tests.spiders.conftest import read_fixture


def test_parse_search_results_extracts_core_listing_fields() -> None:
    payload = json.loads(read_fixture("zillow_next_data.json"))

    results = parse_search_results(payload)

    assert len(results) == 3
    assert results[0]["price_usd_cents"] == 75_000_000
    assert results[0]["area_m2"] == 92.9
    assert results[0]["bedrooms"] == 2
    assert results[1]["hoa_fees_monthly_usd"] is None


def test_parse_listing_detail_extracts_optional_us_fields() -> None:
    payload = json.loads(read_fixture("zillow_next_data.json"))

    listing = parse_listing_detail(payload)

    assert listing["hoa_fees_monthly_usd"] == 25_000
    assert listing["zestimate_usd_cents"] == 77_000_000
    assert listing["lot_size_m2"] == 46.45
    assert listing["school_rating"] == 7.0
