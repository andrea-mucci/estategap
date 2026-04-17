from __future__ import annotations

import pytest

from pipeline.enricher import EnricherService, EnricherSettings, FranceDVFEnricher
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
async def test_eu_pipeline_fr_enriches_listing(asyncpg_pool, normalized_listing_factory) -> None:
    listing = normalized_listing_factory(
        country="FR",
        source="seloger",
        source_id="fr-1",
        source_url="https://www.seloger.com/annonces/123456.htm",
        location_wkt="POINT(2.378 48.864)",
    )
    await ListingWriter(asyncpg_pool).upsert_batch([listing])
    await asyncpg_pool.execute(
        """
        INSERT INTO dvf_transactions (
            date_mutation,
            valeur_fonciere,
            type_local,
            surface_reelle_bati,
            adresse_numero,
            adresse_nom_voie,
            code_postal,
            commune,
            geom
        ) VALUES (
            DATE '2025-03-01',
            580000,
            'Appartement',
            80,
            '10',
            'Rue Oberkampf',
            '75011',
            'Paris',
            ST_GeomFromText('POINT(2.378 48.864)', 4326)
        )
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
    service._enrichers_by_country["FR"] = [FranceDVFEnricher(pool=asyncpg_pool)]

    enriched, status = await service.process_listing(listing)

    assert status == "completed"
    assert enriched.dvf_nearby_count == 1
    assert jetstream.messages

