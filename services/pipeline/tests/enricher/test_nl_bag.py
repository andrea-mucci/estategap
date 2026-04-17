from __future__ import annotations

from unittest.mock import AsyncMock

import httpx
import pytest

from pipeline.enricher.nl_bag import NetherlandsBAGEnricher
from tests.enricher.conftest import listing_factory, read_fixture


@pytest.mark.asyncio
async def test_bag_id_direct_lookup_path() -> None:
    client = AsyncMock()
    client.get.return_value = httpx.Response(
        200,
        text=read_fixture("pdok_response.xml"),
        request=httpx.Request("GET", "https://example.test"),
    )
    enricher = NetherlandsBAGEnricher(client=client)

    result = await enricher.enrich(
        listing_factory(
            country="NL",
            source="funda",
            bag_id="0363100012345678",
            address="Prinsengracht 1",
            postal_code="1015DV",
            location_wkt="POINT(4.9041 52.3676)",
        )
    )

    assert result.status == "completed"
    assert result.updates["bag_id"] == "0363100012345678"
    assert result.updates["year_built"] == 1998


@pytest.mark.asyncio
async def test_address_fallback_path() -> None:
    client = AsyncMock()
    client.get.return_value = httpx.Response(
        200,
        text=read_fixture("pdok_response.xml"),
        request=httpx.Request("GET", "https://example.test"),
    )
    enricher = NetherlandsBAGEnricher(client=client)

    result = await enricher.enrich(
        listing_factory(
            country="NL",
            source="funda",
            bag_id=None,
            address="Prinsengracht 1",
            postal_code="1015DV",
            location_wkt="POINT(4.9041 52.3676)",
        )
    )

    assert result.status == "completed"
    assert result.updates["official_area_m2"] == 102


@pytest.mark.asyncio
async def test_no_match_when_pdok_returns_empty_feature_collection() -> None:
    client = AsyncMock()
    client.get.return_value = httpx.Response(
        200,
        text='<wfs:FeatureCollection xmlns:wfs="http://www.opengis.net/wfs/2.0" />',
        request=httpx.Request("GET", "https://example.test"),
    )
    enricher = NetherlandsBAGEnricher(client=client)

    result = await enricher.enrich(
        listing_factory(country="NL", source="funda", bag_id="0363100012345678", address="Prinsengracht 1", postal_code="1015DV")
    )

    assert result.status == "no_match"

