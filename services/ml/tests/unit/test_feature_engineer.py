from __future__ import annotations

import math

import numpy as np
import pytest

pytest.importorskip("pandas")
pytest.importorskip("sklearn")

from estategap_ml.features.engineer import FeatureEngineer


def test_transform_full_row_returns_finite_matrix(
    sample_training_frame,
    zone_stats_bundle,
) -> None:
    zone_stats, city_stats, country_stats = zone_stats_bundle
    engineer = FeatureEngineer(zone_stats=zone_stats, city_stats=city_stats, country_stats=country_stats)

    matrix = engineer.fit_transform(sample_training_frame)

    assert matrix.shape[0] == 1
    assert np.isfinite(matrix).all()


def test_transform_missing_optionals_stays_finite(
    sample_training_frame,
    zone_stats_bundle,
) -> None:
    zone_stats, city_stats, country_stats = zone_stats_bundle
    engineer = FeatureEngineer(zone_stats=zone_stats, city_stats=city_stats, country_stats=country_stats)
    sparse_frame = sample_training_frame.assign(
        usable_area_m2=np.nan,
        bedrooms=np.nan,
        bathrooms=np.nan,
        floor_number=np.nan,
        total_floors=np.nan,
        parking_spaces=np.nan,
        energy_cert=None,
        condition=None,
        photo_count=np.nan,
    )

    matrix = engineer.fit_transform(sparse_frame)

    assert matrix.shape[0] == 1
    assert np.isfinite(matrix).all()


def test_zone_fallback_uses_city_stats_when_zone_id_missing(
    sample_training_frame,
    zone_stats_bundle,
) -> None:
    zone_stats, city_stats, country_stats = zone_stats_bundle
    engineer = FeatureEngineer(zone_stats=zone_stats, city_stats=city_stats, country_stats=country_stats)
    frame = sample_training_frame.assign(zone_id=None)

    matrix = engineer.fit_transform(frame)
    feature_names = engineer.get_feature_names_out()
    idx = feature_names.index("zone_median_price_m2")

    assert matrix[0, idx] == pytest.approx(4200.0)


def test_cyclical_encoding_for_month_six_matches_expected_phase(
    sample_training_frame,
    zone_stats_bundle,
) -> None:
    zone_stats, city_stats, country_stats = zone_stats_bundle
    engineer = FeatureEngineer(zone_stats=zone_stats, city_stats=city_stats, country_stats=country_stats)

    matrix = engineer.fit_transform(sample_training_frame)
    feature_names = engineer.get_feature_names_out()
    sin_idx = feature_names.index("month_sin")
    cos_idx = feature_names.index("month_cos")

    assert matrix[0, sin_idx] == pytest.approx(1.0, abs=1e-6)
    assert matrix[0, cos_idx] == pytest.approx(0.0, abs=1e-6)
