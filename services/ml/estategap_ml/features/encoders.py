"""Preconfigured ordinal encoders used by the feature engineer."""

from __future__ import annotations

from sklearn.preprocessing import OrdinalEncoder


def _fit_encoder(categories: list[str]) -> OrdinalEncoder:
    encoder = OrdinalEncoder(
        categories=[categories],
        handle_unknown="use_encoded_value",
        unknown_value=0,
        encoded_missing_value=0,
        dtype=float,
    )
    encoder.fit([[value] for value in categories])
    return encoder


def energy_cert_encoder() -> OrdinalEncoder:
    """Return an encoder mapping G..A onto 1..7 and unknowns onto 0."""

    return _fit_encoder(["G", "F", "E", "D", "C", "B", "A"])


def condition_encoder() -> OrdinalEncoder:
    """Return an encoder mapping condition quality onto 1..4 and unknowns onto 0."""

    return _fit_encoder(["to_renovate", "renovate", "good", "new"])
