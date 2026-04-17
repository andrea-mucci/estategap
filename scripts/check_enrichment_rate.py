"""Check enrichment coverage thresholds for country-specific enrichers."""

from __future__ import annotations

import argparse
import asyncio

import asyncpg  # type: ignore[import-untyped]


QUERIES = {
    "dvf": ("dvf_nearby_count", 0.60),
    "land_registry": ("uk_lr_match_count", 0.70),
    "omi": ("omi_zone_code", 0.50),
    "bag": ("bag_id", 0.80),
}


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--country", required=True)
    parser.add_argument("--city")
    parser.add_argument("--enricher", required=True, choices=sorted(QUERIES))
    args = parser.parse_args()

    field, default_threshold = QUERIES[args.enricher]
    pool = await asyncpg.create_pool(args.database_url, min_size=1, max_size=2)
    try:
        async with pool.acquire() as conn:
            where = ["country = $1"]
            params: list[object] = [args.country.upper()]
            if args.city:
                where.append(f"LOWER(city) = ${len(params) + 1}")
                params.append(args.city.lower())
            row = await conn.fetchrow(
                f"""
                SELECT
                    COUNT(*) AS total,
                    COUNT(*) FILTER (WHERE {field} IS NOT NULL) AS matched
                FROM listings
                WHERE {' AND '.join(where)}
                """,
                *params,
            )
        total = int(row["total"] or 0)
        matched = int(row["matched"] or 0)
        rate = matched / total if total else 0.0
        status = "PASS" if rate >= default_threshold else "FAIL"
        print(f"{status}: {args.enricher} coverage = {rate:.2%} ({matched}/{total})")
    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
