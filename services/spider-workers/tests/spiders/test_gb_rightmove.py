from __future__ import annotations

from bs4 import BeautifulSoup

from estategap_spiders.spiders.gb_rightmove_parser import parse_json_ld, parse_uk_fields
from tests.spiders.conftest import read_fixture


def test_json_ld_price_is_gbp() -> None:
    payload = parse_json_ld(read_fixture("gb_rightmove_search.html"))

    assert payload["json_ld"]["offers"]["price"] == 475000
    assert payload["currency"] == "GBP"


def test_css_selector_fields_extract_tenure_and_epc() -> None:
    soup = BeautifulSoup(read_fixture("gb_rightmove_search.html"), "html.parser")
    payload = parse_uk_fields(soup)

    assert payload["councilTaxBand"] == "D"
    assert payload["epcRating"] == "B"
    assert payload["tenure"] == "freehold"
    assert payload["leaseholdYearsRemaining"] is None

