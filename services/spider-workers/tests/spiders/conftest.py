from __future__ import annotations

from pathlib import Path


FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures"


def read_fixture(name: str) -> str:
    return (FIXTURE_DIR / name).read_text(encoding="utf-8")
