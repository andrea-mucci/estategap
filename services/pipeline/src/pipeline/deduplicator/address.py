"""Address normalization helpers for deduplication."""

from __future__ import annotations

import re
import unicodedata


_STOPWORDS = {
    "calle",
    "c",
    "avenida",
    "av",
    "rue",
    "via",
    "street",
    "st",
    "strasse",
    "str",
    "plaza",
    "pza",
}


def normalize_address(raw: str) -> str:
    """Normalize an address for fuzzy matching across portals."""

    decomposed = unicodedata.normalize("NFD", raw or "")
    without_accents = "".join(char for char in decomposed if not unicodedata.combining(char))
    lowered = without_accents.lower()
    alnum_only = re.sub(r"[^a-z0-9\s]", " ", lowered)
    tokens = [token for token in re.split(r"\s+", alnum_only) if token and token not in _STOPWORDS]
    return " ".join(tokens).strip()


__all__ = ["normalize_address"]
