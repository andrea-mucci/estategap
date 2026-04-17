from __future__ import annotations

from estategap_spiders.spiders.fr_leboncoin_parser import parse_search_cards
from tests.spiders.conftest import read_fixture


def test_pro_vs_private_seller_detection() -> None:
    cards = parse_search_cards(read_fixture("fr_leboncoin_search.html"))

    assert cards[0]["owner"]["type"] == "pro"
    assert cards[1]["owner"]["type"] == "private"


def test_rooms_count_is_available_for_pieces_mapping() -> None:
    cards = parse_search_cards(read_fixture("fr_leboncoin_search.html"))

    assert cards[0]["attributes"]["rooms_count"] == 3
    assert cards[1]["attributes"]["rooms_count"] == 5

