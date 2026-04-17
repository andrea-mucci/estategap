from __future__ import annotations

from unittest.mock import AsyncMock

import httpx
import pytest

from pipeline.enricher import EnricherService, EnricherSettings, NetherlandsBAGEnricher
from pipeline.normalizer.writer import ListingWriter
from tests.enricher.conftest import read_fixture


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
async def test_eu_pipeline_nl_enriches_listing(asyncpg_pool, normalized_listing_factory) -> None:
    listing = normalized_listing_factory(
        country="NL",
        source="funda",
        source_id="nl-1",
        source_url="https://www.funda.nl/detail/koop/amsterdam/huis-6001",
        address="Prinsengracht 1",
        postal_code="1015DV",
        bag_id="0363100012345678",
        location_wkt="POINT(4.9041 52.3676)",
    )
    await ListingWriter(asyncpg_pool).upsert_batch([listing])
    client = AsyncMock()
    client.get.return_value = httpx.Response(
        200,
        text=read_fixture("pdok_response.xml"),
        request=httpx.Request("GET", "https://example.test"),
    )

    broker = _FakeBroker()
    service = EnricherService(
        EnricherSettings(database_url="postgresql://unused", kafka_brokers="localhost:9092"),
        pool=asyncpg_pool,
        broker=broker,
        poi_calculator=_FakePOI(),
    )
    service._enrichers_by_country["NL"] = [NetherlandsBAGEnricher(client=client)]

    enriched, status = await service.process_listing(listing)

    assert status == "completed"
    assert enriched.year_built == 1998
    assert broker.messages
