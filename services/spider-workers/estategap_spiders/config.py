"""Spider runtime constants and configuration re-exports."""

from __future__ import annotations

from .settings import Config

RATE_LIMITS: dict[str, float] = {
    "zillow": 3.0,
    "redfin": 2.0,
    "realtor_com": 1.5,
}
USE_RESIDENTIAL_PROXY: dict[str, bool] = {
    "zillow": True,
    "redfin": False,
    "realtor_com": False,
}

__all__ = ["Config", "RATE_LIMITS", "USE_RESIDENTIAL_PROXY"]
