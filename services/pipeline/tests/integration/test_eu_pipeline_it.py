from __future__ import annotations

from decimal import Decimal

import pytest

from pipeline.enricher import EnricherService, EnricherSettings, ItalyOMIEnricher
from pipeline.normalizer.writer import ListingWriter


class _FakeJetStream:
    def __init__(self) -> None:
        self.messages: list[tuple[str, bytes]] = []

    async def publish(self, subject: str, payload: bytes) -> None:
        self.messages.append((subject, payload))


class _FakePOI:
    async def calculate(self, listing) -> dict[str, int | None]:
        del listing
        return {}


@pytest.mark.asyncio
async def test_eu_pipeline_it_enriches_listing(asyncpg_pool, normalized_listing_factory) -> None:
    listing = normalized_listing_factory(
        country="IT",
        source="immobiliare",
        source_id="it-1",
        source_url="https://www.immobiliare.it/annunci/1001/",
        location_wkt="POINT(12.4964 41.9028)",
        asking_price=Decimal("360000"),
        asking_price_eur=Decimal("360000"),
        built_area_m2=Decimal("90"),
    )
    await ListingWriter(asyncpg_pool).upsert_batch([listing])
    await asyncpg_pool.execute(
        """
        INSERT INTO omi_zones (zona_omi, period, tipologia, price_min, price_max, geometry)
        VALUES ('B1', '2024-H2', 'abitazioni civili', 3500, 4500, ST_GeomFromText('MULTIPOLYGON(((12.49 41.90, 12.50 41.90, 12.50 41.91, 12.49 41.91, 12.49 41.90)))', 4326))
        """
    )

    jetstream = _FakeJetStream()
    service = EnricherService(
        EnricherSettings(database_url="postgresql://unused", nats_url="nats://unused"),
        pool=asyncpg_pool,
        jetstream=jetstream,
        nats_client=jetstream,
        poi_calculator=_FakePOI(),
    )
    service._enrichers_by_country["IT"] = [ItalyOMIEnricher(pool=asyncpg_pool)]

    enriched, status = await service.process_listing(listing)

    assert status == "completed"
    assert enriched.omi_zone_code == "B1"
    assert jetstream.messages

