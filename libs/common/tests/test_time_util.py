from __future__ import annotations

from datetime import UTC, datetime

from estategap_common.time_util import now


def test_now_uses_override(monkeypatch) -> None:
    monkeypatch.setenv("NOW_OVERRIDE", "1745000000")
    assert now() == datetime.fromtimestamp(1745000000, tz=UTC)


def test_now_falls_back_for_invalid_override(monkeypatch) -> None:
    monkeypatch.setenv("NOW_OVERRIDE", "invalid")
    current = now()
    assert current.tzinfo == UTC
