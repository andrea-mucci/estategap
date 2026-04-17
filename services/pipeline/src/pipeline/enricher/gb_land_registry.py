"""UK Land Registry Price Paid enricher."""

from __future__ import annotations

import re
from decimal import Decimal

import asyncpg  # type: ignore[import-untyped]
import structlog
from rapidfuzz import fuzz

from estategap_common.models import NormalizedListing

from .base import BaseEnricher, EnrichmentResult, register_enricher


LOGGER = structlog.get_logger(__name__)
WORD_RE = re.compile(r"[^a-z0-9]+")


@register_enricher("GB")
class UKLandRegistryEnricher(BaseEnricher):
    """Match UK listings to the Price Paid dataset using postcode + fuzzy address."""

    def __init__(self, *, pool: asyncpg.Pool | None = None) -> None:
        self._pool = pool

    async def enrich(self, listing: NormalizedListing) -> EnrichmentResult:
        if self._pool is None or listing.postal_code is None or listing.address is None:
            return EnrichmentResult(status="no_match")
        try:
            rows = await self._fetch_rows(listing.postal_code)
            normalized_listing_address = normalize_uk_address(listing.address, listing.postal_code)
            matches = []
            for row in rows:
                candidate = normalize_uk_address(str(row.get("address_normalized") or ""), listing.postal_code)
                score = fuzz.token_sort_ratio(normalized_listing_address, candidate)
                if score >= 90:
                    matches.append((score, row))
            if not matches:
                return EnrichmentResult(status="no_match", updates={"uk_lr_match_count": 0})
            matches.sort(key=lambda item: str(item[1].get("date_transfer") or ""), reverse=True)
            newest = matches[0][1]
            return EnrichmentResult(
                status="completed",
                updates={
                    "uk_lr_match_count": len(matches),
                    "uk_lr_last_price_gbp": newest.get("price_gbp"),
                    "uk_lr_last_date": newest.get("date_transfer"),
                },
            )
        except Exception as exc:  # noqa: BLE001
            LOGGER.error("uk_land_registry_failed", listing_id=str(listing.id), error=str(exc))
            return EnrichmentResult(status="failed", error=str(exc))

    async def _fetch_rows(self, postcode: str) -> list[dict[str, object]]:
        if self._pool is None:
            return []
        async with self._pool.acquire() as conn:
            records = await conn.fetch(
                """
                SELECT transaction_uid, price_gbp, date_transfer, address_normalized
                FROM uk_price_paid
                WHERE postcode = $1
                ORDER BY date_transfer DESC
                LIMIT 100
                """,
                postcode.strip().upper(),
            )
        return [dict(record) for record in records]


def normalize_uk_address(address: str, postcode: str | None = None) -> str:
    text = address.lower()
    if postcode:
        text = f"{text} {postcode.lower()}"
    text = WORD_RE.sub(" ", text)
    replacements = {
        " road ": " rd ",
        " street ": " st ",
        " avenue ": " ave ",
        " apartment ": " flat ",
    }
    for source, target in replacements.items():
        text = text.replace(source, target)
    return " ".join(text.split())


__all__ = ["UKLandRegistryEnricher", "normalize_uk_address"]
