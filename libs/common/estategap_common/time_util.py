"""Shared time helpers that respect the deterministic test-mode clock override."""

from __future__ import annotations

import os
from datetime import UTC, datetime


def now() -> datetime:
    raw = os.getenv("NOW_OVERRIDE", "").strip()
    if raw:
        try:
            return datetime.fromtimestamp(int(raw), tz=UTC)
        except ValueError:
            pass
    return datetime.now(tz=UTC)


__all__ = ["now"]
