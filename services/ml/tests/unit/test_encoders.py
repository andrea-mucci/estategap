from __future__ import annotations

import pytest

pytest.importorskip("sklearn")

from estategap_ml.features.encoders import condition_encoder, energy_cert_encoder


def test_energy_cert_encoder_maps_expected_values() -> None:
    encoder = energy_cert_encoder()
    values = encoder.transform([["A"], ["G"], ["unknown"]]).reshape(-1).tolist()
    assert values == [7.0, 1.0, 0.0]


def test_condition_encoder_maps_expected_values() -> None:
    encoder = condition_encoder()
    values = encoder.transform([["new"], ["to_renovate"], ["mystery"]]).reshape(-1).tolist()
    assert values == [4.0, 1.0, 0.0]


def test_both_encoders_handle_none_without_raising() -> None:
    assert energy_cert_encoder().transform([[None]]).item() == 0.0
    assert condition_encoder().transform([[None]]).item() == 0.0
