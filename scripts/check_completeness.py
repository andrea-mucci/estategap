"""Check portal completeness against expected-field thresholds."""

from __future__ import annotations

import argparse
import asyncio
import sys
from decimal import Decimal
from pathlib import Path

import asyncpg  # type: ignore[import-untyped]

REPO_ROOT = Path(__file__).resolve().parents[1]
PIPELINE_SRC = REPO_ROOT / "services" / "pipeline" / "src"
if str(PIPELINE_SRC) not in sys.path:
    sys.path.insert(0, str(PIPELINE_SRC))

from pipeline.normalizer.mapper import PortalMapper


def compute_row_completeness(row: asyncpg.Record, expected_fields: tuple[str, ...]) -> float:
    if not expected_fields:
        return 0.0
    present = 0
    for field in expected_fields:
        value = row[field]
        if value is None:
            continue
        if isinstance(value, Decimal) and value == 0:
            continue
        present += 1
    return round(present / len(expected_fields), 4)


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--country", required=True)
    parser.add_argument("--portal", required=True)
    parser.add_argument("--threshold", type=float, default=0.75)
    args = parser.parse_args()

    mappings_dir = Path(__file__).resolve().parents[1] / "services" / "pipeline" / "config" / "mappings"
    mapper = PortalMapper(PortalMapper.load_all(mappings_dir))
    mapping = mapper.get(args.country, args.portal)
    if mapping is None:
        raise SystemExit(f"No mapping found for {args.country}:{args.portal}")
    pool = await asyncpg.create_pool(args.database_url, min_size=1, max_size=2)
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                f"""
                SELECT {", ".join(sorted(set(mapping.expected_fields)))}
                FROM listings
                WHERE country = $1 AND source = $2
                ORDER BY updated_at DESC
                LIMIT 500
                """,
                args.country.upper(),
                args.portal,
            )
        scores = [compute_row_completeness(row, mapping.expected_fields) for row in rows]
        average = sum(scores) / len(scores) if scores else 0.0
        status = "PASS" if average >= args.threshold else "FAIL"
        print(f"{status}: {args.country.upper()} {args.portal} average completeness = {average:.2%}")
    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
