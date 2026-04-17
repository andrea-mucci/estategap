from __future__ import annotations

from estategap_spiders.spiders.fr_seloger_parser import parse_json_ld, parse_search_page
from tests.spiders.conftest import read_fixture


def test_json_ld_extraction_and_dpe() -> None:
    payload = parse_json_ld(read_fixture("fr_seloger_detail.html"))

    assert payload["json_ld"]["numberOfRooms"] == 4
    assert payload["energyEfficiencyScaleMin"] == "C"
    assert payload["url"] == "https://www.seloger.com/annonces/vente/appartement/paris-75/123456.htm"


def test_search_page_finds_detail_urls() -> None:
    items = parse_search_page(read_fixture("fr_seloger_detail.html"))

    assert items == [
        {"url": "https://www.seloger.com/annonces/vente/appartement/paris-75/123456.htm"}
    ]
