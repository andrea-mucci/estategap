from __future__ import annotations

from estategap_spiders.spiders.fr_bienici_parser import extract_preloaded_state, parse_listing
from tests.spiders.conftest import read_fixture


def test_extract_preloaded_state() -> None:
    state = extract_preloaded_state(read_fixture("fr_bienici_search.html"))

    assert len(state["listings"]) == 1


def test_parse_listing_exposes_piece_count_and_location() -> None:
    state = extract_preloaded_state(read_fixture("fr_bienici_search.html"))
    payload = parse_listing(state["listings"][0])

    assert payload["bien"]["nbPieces"] == 4
    assert payload["bien"]["dpe"]["classe"] == "B"
    assert payload["url"] == "https://www.bienici.com/annonce/4001"

