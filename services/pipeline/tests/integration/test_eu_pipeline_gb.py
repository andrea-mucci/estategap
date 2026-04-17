from __future__ import annotations

from decimal import Decimal

import pytest

from pipeline.enricher import EnricherService, EnricherSettings, UKLandRegistryEnricher
from pipeline.normalizer.writer import ListingWriter


class _FakeBroker:
    def __init__(self) -> None:
        self.messages: list[tuple[str, str, bytes]] = []

    async def publish(self, topic: str, key: str, payload: bytes) -> None:
        self.messages.append((topic, key, payload))


class _FakePOI:
    async def calculate(self, listing) -> dict[str, int | None]:
        del listing
        return {}


@pytest.mark.asyncio
async def test_eu_pipeline_gb_enriches_listing(asyncpg_pool, normalized_listing_factory) -> None:
    listing = normalized_listing_factory(
        country="GB",
        source="rightmove",
        source_id="gb-1",
        source_url="https://www.rightmove.co.uk/properties/5001",
        address="21 Baker Street",
        postal_code="NW1 6XE",
        location_wkt="POINT(-0.1585 51.5237)",
        asking_price=Decimal("475000"),
        currency="GBP",
        asking_price_eur=Decimal("555750"),
    )
    await ListingWriter(asyncpg_pool).upsert_batch([listing])
    await asyncpg_pool.execute(
        """
        INSERT INTO uk_price_paid (
            transaction_uid,
            price_gbp,
            date_transfer,
            postcode,
            property_type,
            old_new,
            tenure,
            paon,
            saon,
            street,
            locality,
            town_city,
            district,
            county,
            address_normalized
        ) VALUES (
            '00000000-0000-0000-0000-000000000001',
            475000,
            DATE '2024-09-20',
            'NW1 6XE',
            'D',
            'N',
            'F',
            '21',
            NULL,
            'Baker Street',
            NULL,
            'London',
            'Westminster',
            'Greater London',
            '21 baker st london nw1 6xe'
        )
        """
    )

    broker = _FakeBroker()
    service = EnricherService(
        EnricherSettings(database_url="postgresql://unused", kafka_brokers="localhost:9092"),
        pool=asyncpg_pool,
        broker=broker,
        poi_calculator=_FakePOI(),
    )
    service._enrichers_by_country["GB"] = [UKLandRegistryEnricher(pool=asyncpg_pool)]

    enriched, status = await service.process_listing(listing)

    assert status == "completed"
    assert enriched.uk_lr_last_price_gbp == 475000
    assert broker.messages
