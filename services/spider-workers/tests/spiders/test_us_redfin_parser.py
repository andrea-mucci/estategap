from __future__ import annotations

import json

from estategap_spiders.spiders.us_redfin_parser import parse_above_fold, parse_school_data
from tests.spiders.conftest import read_fixture


def test_parse_above_fold_extracts_compete_score_and_area_conversion() -> None:
    payload = json.loads(read_fixture("redfin_above_fold.json"))

    listing = parse_above_fold(payload)

    assert listing["compete_score"] == 84
    assert listing["price_usd_cents"] == 88_000_000
    assert listing["area_sqft"] == 1200.0
    assert listing["area_m2"] == 111.48


def test_parse_school_data_returns_average_rating() -> None:
    payload = json.loads(read_fixture("redfin_above_fold.json"))

    rating = parse_school_data(payload["payload"]["schoolsData"])

    assert rating == 7.0
