from __future__ import annotations

from decimal import Decimal

import pytest

from pipeline.enricher import EnricherService, EnricherSettings, POIDistanceCalculator
from pipeline.enricher.catastro import SpainCatastroEnricher
from pipeline.normalizer.writer import ListingWriter
from tests.conftest import FakeMsg


GML_FIXTURE = """\
<wfs:FeatureCollection
    xmlns:wfs="http://www.opengis.net/wfs/2.0"
    xmlns:cp="http://inspire.jrc.ec.europa.eu/schemas/cp/4.0"
    xmlns:base="http://inspire.jrc.ec.europa.eu/schemas/base/3.3"
    xmlns:bu-base="http://inspire.jrc.ec.europa.eu/schemas/bu-base/4.0"
    xmlns:gml="http://www.opengis.net/gml/3.2">
  <wfs:member>
    <cp:CadastralParcel>
      <cp:inspireId>
        <base:Identifier>
          <base:localId>3665603VK4736D0001UY</base:localId>
        </base:Identifier>
      </cp:inspireId>
      <cp:areaValue>118.5</cp:areaValue>
      <cp:geometry>
        <gml:Polygon>
          <gml:exterior>
            <gml:LinearRing>
              <gml:posList>
                -3.7042 40.4165 -3.7035 40.4165 -3.7035 40.4171 -3.7042 40.4171 -3.7042 40.4165
              </gml:posList>
            </gml:LinearRing>
          </gml:exterior>
        </gml:Polygon>
      </cp:geometry>
      <bu-base:yearOfConstruction>1952</bu-base:yearOfConstruction>
    </cp:CadastralParcel>
  </wfs:member>
</wfs:FeatureCollection>
"""


class FakeBroker:
    def __init__(self) -> None:
        self.published: list[tuple[str, str, bytes]] = []

    async def publish(self, topic: str, key: str, payload: bytes) -> None:
        self.published.append((topic, key, payload))


@pytest.mark.asyncio
async def test_enricher_updates_listing_and_publishes_message(
    asyncpg_pool,
    normalized_listing_factory,
    monkeypatch,
) -> None:
    listing = normalized_listing_factory(year_built=None, built_area_m2=Decimal("120"))
    writer = ListingWriter(asyncpg_pool)
    await writer.upsert_batch([listing])
    async with asyncpg_pool.acquire() as conn:
        await conn.executemany(
            """
            INSERT INTO pois (osm_id, country, category, name, location)
            VALUES ($1, $2, $3, $4, ST_GeomFromText($5, 4326))
            """,
            [
                (1, "ES", "metro", "Metro A", "POINT(-3.7037 40.4169)"),
                (2, "ES", "metro", "Metro B", "POINT(-3.7040 40.4171)"),
                (3, "ES", "metro", "Metro C", "POINT(-3.7039 40.4167)"),
                (4, "ES", "train", "Train A", "POINT(-3.7020 40.4180)"),
                (5, "ES", "airport", "Airport A", "POINT(-3.5600 40.4983)"),
                (6, "ES", "park", "Park A", "POINT(-3.7048 40.4155)"),
                (7, "ES", "beach", "Beach A", "POINT(-0.0500 39.9800)"),
            ],
        )

    async def _fake_fetch(self, lon: float, lat: float) -> str:
        return GML_FIXTURE

    monkeypatch.setattr(SpainCatastroEnricher, "_fetch_features", _fake_fetch)

    broker = FakeBroker()
    settings = EnricherSettings(database_url="postgresql://unused", kafka_brokers="localhost:9092")
    service = EnricherService(
        settings,
        pool=asyncpg_pool,
        broker=broker,
        poi_calculator=POIDistanceCalculator(
            pool=asyncpg_pool,
            overpass_url="https://example.test",
            overpass_cache={},
        ),
    )
    message = FakeMsg(listing.model_dump_json().encode())

    await service.handle_message(message)

    row = await asyncpg_pool.fetchrow(
        """
        SELECT cadastral_ref, official_built_area_m2, area_discrepancy_flag, dist_metro_m, enrichment_status
        FROM listings
        WHERE id = $1 AND country = $2
        """,
        listing.id,
        listing.country,
    )

    assert row is not None
    assert row["cadastral_ref"] == "3665603VK4736D0001UY"
    assert row["official_built_area_m2"] == Decimal("118.50")
    assert row["area_discrepancy_flag"] is False
    assert row["dist_metro_m"] is not None
    assert row["enrichment_status"] == "completed"
    assert broker.published
    assert listing.source_id in broker.published[0][2].decode()

    await service.close()
