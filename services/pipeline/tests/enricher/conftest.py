from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from estategap_common.models import NormalizedListing, PropertyCategory


FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"


def read_fixture(name: str) -> str:
    return (FIXTURE_DIR / name).read_text(encoding="utf-8")


class FakeConnection:
    def __init__(self, *, rows=None, row=None) -> None:
        self.rows = rows or []
        self.row = row

    async def fetch(self, *args, **kwargs):
        return self.rows

    async def fetchrow(self, *args, **kwargs):
        return self.row


class _Acquire:
    def __init__(self, connection: FakeConnection) -> None:
        self.connection = connection

    async def __aenter__(self) -> FakeConnection:
        return self.connection

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None


class FakePool:
    def __init__(self, *, rows=None, row=None) -> None:
        self.connection = FakeConnection(rows=rows, row=row)

    def acquire(self) -> _Acquire:
        return _Acquire(self.connection)


def listing_factory(**overrides: object) -> NormalizedListing:
    payload: dict[str, object] = {
        "id": uuid4(),
        "country": "FR",
        "source": "seloger",
        "source_id": "listing-1",
        "source_url": "https://example.test/listing-1",
        "address": "10 Rue Oberkampf",
        "city": "Paris",
        "region": "Île-de-France",
        "postal_code": "75011",
        "location_wkt": "POINT(2.378 48.864)",
        "asking_price": Decimal("615000"),
        "currency": "EUR",
        "asking_price_eur": Decimal("615000"),
        "property_category": PropertyCategory.RESIDENTIAL,
        "property_type": "residential",
        "built_area_m2": Decimal("88"),
        "first_seen_at": datetime(2026, 4, 17, 12, 0, tzinfo=UTC),
        "last_seen_at": datetime(2026, 4, 17, 12, 0, tzinfo=UTC),
    }
    payload.update(overrides)
    return NormalizedListing.model_validate(payload)
