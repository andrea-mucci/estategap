from __future__ import annotations

import pytest

from pipeline.deduplicator.address import normalize_address


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Calle Mayor 5", "mayor 5"),
        ("C./ de la Princesa 2", "de la princesa 2"),
        ("Rue de l'Église 7", "de l eglise 7"),
        ("Street Baker 221B", "baker 221b"),
        ("", ""),
        ("already clean 9", "already clean 9"),
    ],
)
def test_normalize_address(raw: str, expected: str) -> None:
    assert normalize_address(raw) == expected
