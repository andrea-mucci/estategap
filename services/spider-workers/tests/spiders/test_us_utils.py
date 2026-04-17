from __future__ import annotations

import pytest

from estategap_spiders.spiders.us_utils import sqft_to_m2


@pytest.mark.parametrize(
    ("sqft", "expected"),
    [
        (1000, 92.90),
        (500, 46.45),
        (2500, 232.26),
        (0, 0.0),
    ],
)
def test_sqft_to_m2_matches_expected_vectors(sqft: int, expected: float) -> None:
    result = sqft_to_m2(sqft)

    assert result is not None
    assert abs(result - expected) <= 0.01
