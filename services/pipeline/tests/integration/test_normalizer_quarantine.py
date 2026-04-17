from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from estategap_common.models import RawListing

from pipeline.normalizer.config import NormalizerSettings
from pipeline.normalizer.consumer import NormalizerService
from pipeline.normalizer.mapper import PortalMapper
from pipeline.normalizer.writer import ListingWriter


class FakeBroker:
    def __init__(self) -> None:
        self.published: list[tuple[str, str, bytes]] = []

    async def publish(self, topic: str, key: str, payload: bytes) -> None:
        self.published.append((topic, key, payload))


class FakeMessage:
    def __init__(self, payload: bytes) -> None:
        self.data = payload
        self.value = payload
        self.headers: dict[str, str] = {}


@pytest.fixture
def normalizer_settings(database_url: str) -> NormalizerSettings:
    repo_root = Path(__file__).resolve().parents[4]
    return NormalizerSettings.model_construct(
        database_url=database_url,
        kafka_brokers="localhost:9092",
        kafka_topic_prefix="estategap.",
        kafka_max_retries=3,
        batch_size=1,
        batch_timeout=0.01,
        mappings_dir=repo_root / "services" / "pipeline" / "config" / "mappings",
        metrics_port=9101,
        log_level="INFO",
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("message", "expected_reason", "expected_error_fragment"),
    [
        (
            RawListing(
                external_id="bad-price",
                portal="idealista",
                country_code="ES",
                raw_json={
                    "precio": 0,
                    "tipologia": "piso",
                    "superficie": 80,
                    "habitaciones": 3,
                    "banos": 2,
                    "latitud": 40.4168,
                    "longitud": -3.7038,
                    "url": "https://www.idealista.com/inmueble/bad-price/",
                    "municipio": "Madrid",
                    "provincia": "Madrid",
                    "codigoPostal": "28013",
                },
                scraped_at=datetime(2026, 4, 17, 12, 0, tzinfo=UTC),
            ).model_dump_json().encode(),
            "invalid_price",
            None,
        ),
        (
            RawListing(
                external_id="missing-location",
                portal="idealista",
                country_code="ES",
                raw_json={
                    "precio": 100000,
                    "tipologia": "piso",
                    "superficie": 80,
                    "habitaciones": 3,
                    "banos": 2,
                    "url": "https://www.idealista.com/inmueble/missing-location/",
                    "municipio": "Madrid",
                    "provincia": "Madrid",
                    "codigoPostal": "28013",
                },
                scraped_at=datetime(2026, 4, 17, 12, 0, tzinfo=UTC),
            ).model_dump_json().encode(),
            "missing_location",
            None,
        ),
        (
            RawListing(
                external_id="unknown-portal",
                portal="unknown-portal",
                country_code="ES",
                raw_json={"price": 100000},
                scraped_at=datetime(2026, 4, 17, 12, 0, tzinfo=UTC),
            ).model_dump_json().encode(),
            "no_mapping_config",
            None,
        ),
        (
            b'{"external_id": "broken"',
            "invalid_json",
            "Expecting",
        ),
        (
            RawListing(
                external_id="negative-area",
                portal="idealista",
                country_code="ES",
                raw_json={
                    "precio": 100000,
                    "tipologia": "piso",
                    "superficie": -80,
                    "habitaciones": 3,
                    "banos": 2,
                    "latitud": 40.4168,
                    "longitud": -3.7038,
                    "url": "https://www.idealista.com/inmueble/negative-area/",
                    "municipio": "Madrid",
                    "provincia": "Madrid",
                    "codigoPostal": "28013",
                },
                scraped_at=datetime(2026, 4, 17, 12, 0, tzinfo=UTC),
            ).model_dump_json().encode(),
            "validation_error",
            "built_area_m2",
        ),
    ],
)
async def test_normalizer_quarantine_paths(
    asyncpg_pool,
    normalizer_settings: NormalizerSettings,
    message: bytes,
    expected_reason: str,
    expected_error_fragment: str | None,
) -> None:
    broker = FakeBroker()
    service = NormalizerService(
        settings=normalizer_settings,
        mapper=PortalMapper(PortalMapper.load_all(normalizer_settings.mappings_dir)),
        writer=ListingWriter(asyncpg_pool),
        broker=broker,
    )
    fake_message = FakeMessage(message)

    await service.handle_message(fake_message)

    quarantine_row = await asyncpg_pool.fetchrow(
        "SELECT reason, error_detail FROM quarantine ORDER BY id DESC LIMIT 1"
    )
    listings_count = await asyncpg_pool.fetchval("SELECT COUNT(*) FROM listings")

    assert broker.published == []
    assert listings_count == 0
    assert quarantine_row is not None
    assert quarantine_row["reason"] == expected_reason
    if expected_error_fragment is not None:
        assert expected_error_fragment in (quarantine_row["error_detail"] or "")
