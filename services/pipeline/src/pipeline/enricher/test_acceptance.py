"""Manual acceptance helper for Catastro enrichment."""

from __future__ import annotations

import argparse
import asyncio
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from estategap_common.models import NormalizedListing

from .catastro import SpainCatastroEnricher


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a live Catastro enrichment lookup")
    parser.add_argument("--lat", required=True, type=float)
    parser.add_argument("--lon", required=True, type=float)
    parser.add_argument("--portal-area", required=True, type=Decimal)
    return parser.parse_args()


async def _run(args: argparse.Namespace) -> None:
    listing = NormalizedListing.model_validate(
        {
            "id": uuid4(),
            "country": "ES",
            "source": "acceptance",
            "source_id": str(uuid4()),
            "source_url": "https://example.test/listing",
            "location_wkt": f"POINT({args.lon} {args.lat})",
            "asking_price": Decimal("1"),
            "currency": "EUR",
            "asking_price_eur": Decimal("1"),
            "built_area_m2": args.portal_area,
            "first_seen_at": datetime.now(UTC),
            "last_seen_at": datetime.now(UTC),
        }
    )
    enricher = SpainCatastroEnricher()
    try:
        result = await enricher.enrich(listing)
    finally:
        await enricher.aclose()
    print(f"status: {result.status}")
    print(f"cadastral_ref: {result.updates.get('cadastral_ref')}")
    print(f"official_built_area_m2: {result.updates.get('official_built_area_m2')}")
    print(f"area_discrepancy_flag: {result.updates.get('area_discrepancy_flag')}")
    print(f"year_built: {result.updates.get('year_built')}")


def main() -> None:
    asyncio.run(_run(_parse_args()))


if __name__ == "__main__":
    main()
