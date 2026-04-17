from __future__ import annotations

import logging

import pytest

pytest.importorskip("yaml")
pytest.importorskip("pydantic")

from estategap_ml.config import CONFIG_DIR
from estategap_ml.features.config import CountryFeatureConfig
from estategap_ml.features.engineer import FeatureEngineer


@pytest.mark.parametrize(
    ("country", "expected_feature"),
    [
        ("es", "energy_cert_encoded"),
        ("it", "ape_rating"),
        ("fr", "dpe_rating"),
        ("gb", "council_tax_band_encoded"),
        ("us", "hoa_fees_monthly_usd"),
        ("nl", "is_new_construction"),
    ],
)
def test_country_feature_config_loads_expected_features(country: str, expected_feature: str) -> None:
    config = CountryFeatureConfig.from_yaml(CONFIG_DIR / f"features_{country}.yaml")

    assert config.country == country
    assert expected_feature in config.all_features


def test_missing_country_config_falls_back_to_base_and_logs_warning(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING):
        config = FeatureEngineer._load_feature_config("ZZ")

    assert config.country == "base"
    assert "feature_config_fallback" in caplog.text
