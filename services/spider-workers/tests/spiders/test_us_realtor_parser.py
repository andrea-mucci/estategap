from __future__ import annotations

from estategap_spiders.spiders._eu_utils import load_json_ld_blocks
from estategap_spiders.spiders.us_realtor_parser import parse_json_ld, parse_window_data
from tests.spiders.conftest import read_fixture


def test_parse_json_ld_extracts_mls_school_district_and_price() -> None:
    html = read_fixture("realtor_listing.html")

    listing = parse_json_ld(load_json_ld_blocks(html))

    assert listing["mls_id"] == "MLS-1000"
    assert listing["school_district"] == "District 2"
    assert listing["price_usd_cents"] == 79_900_000


def test_parse_window_data_extracts_crime_index() -> None:
    html = read_fixture("realtor_listing.html")

    payload = parse_window_data(html)

    assert payload["crime_index"] == 12.5
