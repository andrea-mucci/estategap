from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock
from uuid import uuid4

import httpx
import pytest

from estategap_common.models import NormalizedListing
from pipeline.enricher.catastro import SpainCatastroEnricher


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

EMPTY_FIXTURE = """\
<wfs:FeatureCollection xmlns:wfs="http://www.opengis.net/wfs/2.0" />
"""


def _listing(*, built_area_m2: str = "120", year_built: int | None = None) -> NormalizedListing:
    return NormalizedListing.model_validate(
        {
            "id": uuid4(),
            "country": "ES",
            "source": "idealista",
            "source_id": "listing-123",
            "source_url": "https://www.idealista.com/inmueble/listing-123/",
            "location_wkt": "POINT(-3.7038 40.4168)",
            "asking_price": Decimal("450000"),
            "currency": "EUR",
            "asking_price_eur": Decimal("450000"),
            "built_area_m2": Decimal(built_area_m2),
            "year_built": year_built,
            "first_seen_at": datetime(2026, 4, 17, 12, 0, tzinfo=UTC),
            "last_seen_at": datetime(2026, 4, 17, 12, 0, tzinfo=UTC),
        }
    )


@pytest.mark.asyncio
async def test_catastro_enricher_extracts_expected_fields() -> None:
    client = AsyncMock()
    client.get.return_value = httpx.Response(
        200,
        text=GML_FIXTURE,
        request=httpx.Request("GET", "http://example.test"),
    )
    enricher = SpainCatastroEnricher(client=client)

    result = await enricher.enrich(_listing())

    assert result.status == "completed"
    assert result.updates["cadastral_ref"] == "3665603VK4736D0001UY"
    assert result.updates["official_built_area_m2"] == Decimal("118.5")
    assert result.updates["year_built"] == 1952
    assert result.updates["building_geometry_wkt"].startswith("POLYGON")
    assert result.updates["area_discrepancy_flag"] is False


@pytest.mark.asyncio
async def test_catastro_enricher_flags_area_discrepancy() -> None:
    client = AsyncMock()
    client.get.return_value = httpx.Response(
        200,
        text=GML_FIXTURE,
        request=httpx.Request("GET", "http://example.test"),
    )
    enricher = SpainCatastroEnricher(client=client)

    result = await enricher.enrich(_listing(built_area_m2="150"))

    assert result.status == "completed"
    assert result.updates["area_discrepancy_flag"] is True


@pytest.mark.asyncio
async def test_catastro_enricher_returns_no_match_when_wfs_is_empty() -> None:
    client = AsyncMock()
    client.get.return_value = httpx.Response(
        200,
        text=EMPTY_FIXTURE,
        request=httpx.Request("GET", "http://example.test"),
    )
    enricher = SpainCatastroEnricher(client=client)

    result = await enricher.enrich(_listing())

    assert result.status == "no_match"
    assert result.updates == {}


@pytest.mark.asyncio
async def test_catastro_enricher_returns_failed_when_httpx_raises() -> None:
    request = httpx.Request("GET", "http://example.test")
    client = AsyncMock()
    client.get.side_effect = httpx.ConnectError("boom", request=request)
    enricher = SpainCatastroEnricher(client=client)

    result = await enricher.enrich(_listing())

    assert result.status == "failed"
    assert result.error == "boom"
