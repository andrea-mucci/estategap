from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "libs" / "common"))

from estategap_common.models import AlertRule, Listing, ScoringResult, User


FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"


def _load_fixture(name: str) -> dict[str, Any]:
    return json.loads((FIXTURE_DIR / name).read_text())


def _assert_expected_fields(actual: dict[str, Any], expected: dict[str, Any]) -> None:
    for key, expected_value in expected.items():
        assert key in actual
        assert actual[key] == expected_value


def test_listing_roundtrip() -> None:
    expected = _load_fixture("listing.json")
    model = Listing.model_validate_json((FIXTURE_DIR / "listing.json").read_text())
    actual = json.loads(model.model_dump_json())

    _assert_expected_fields(actual, expected)


def test_scoring_result_roundtrip() -> None:
    expected = _load_fixture("scoring_result.json")
    model = ScoringResult.model_validate_json((FIXTURE_DIR / "scoring_result.json").read_text())
    actual = json.loads(model.model_dump_json())

    _assert_expected_fields(actual, expected)


def test_user_roundtrip() -> None:
    expected = _load_fixture("user.json")
    model = User.model_validate_json((FIXTURE_DIR / "user.json").read_text())
    actual = json.loads(model.model_dump_json())

    _assert_expected_fields(actual, expected)
    assert actual["deleted_at"] is None


def test_alert_rule_roundtrip() -> None:
    expected = _load_fixture("alert_rule.json")
    model = AlertRule.model_validate_json((FIXTURE_DIR / "alert_rule.json").read_text())
    actual = json.loads(model.model_dump_json())

    _assert_expected_fields(actual, expected)
    assert actual["filters"] == expected["filters"]
