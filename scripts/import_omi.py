"""Download and import Italy OMI price-band data."""

from __future__ import annotations

import argparse
import asyncio
import csv
import io
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import asyncpg  # type: ignore[import-untyped]
import httpx


OMI_URL_TEMPLATE = "https://www.agenziaentrate.gov.it/omi/{period}.csv"


def parse_omi_rows(handle: io.TextIOBase, *, period: str) -> list[tuple[Any, ...]]:
    reader = csv.DictReader(handle)
    rows: list[tuple[Any, ...]] = []
    for row in reader:
        rows.append(
            (
                row.get("zona_omi"),
                row.get("comune_istat"),
                row.get("comune_name"),
                period,
                row.get("tipologia"),
                row.get("fascia"),
                float(row["price_min"]) if row.get("price_min") else None,
                float(row["price_max"]) if row.get("price_max") else None,
                row.get("geometry_wkt"),
            )
        )
    return rows


async def import_omi_records(pool: asyncpg.Pool, records: Iterable[tuple[Any, ...]]) -> None:
    async with pool.acquire() as conn:
        await conn.executemany(
            """
            INSERT INTO omi_zones (
                zona_omi,
                comune_istat,
                comune_name,
                period,
                tipologia,
                fascia,
                price_min,
                price_max,
                geometry
            ) VALUES (
                $1,
                $2,
                $3,
                $4,
                $5,
                $6,
                $7,
                $8,
                CASE WHEN $9 IS NULL THEN NULL ELSE ST_GeomFromText($9, 4326) END
            )
            ON CONFLICT (zona_omi, period, tipologia) DO UPDATE SET
                comune_istat = EXCLUDED.comune_istat,
                comune_name = EXCLUDED.comune_name,
                fascia = EXCLUDED.fascia,
                price_min = EXCLUDED.price_min,
                price_max = EXCLUDED.price_max,
                geometry = COALESCE(EXCLUDED.geometry, omi_zones.geometry),
                loaded_at = NOW()
            """,
            list(records),
        )


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--period", required=True)
    parser.add_argument("--input-file")
    args = parser.parse_args()

    pool = await asyncpg.create_pool(args.database_url, min_size=1, max_size=2)
    try:
        if args.input_file:
            text = Path(args.input_file).read_text(encoding="utf-8")
            await import_omi_records(pool, parse_omi_rows(io.StringIO(text), period=args.period))
            return
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.get(OMI_URL_TEMPLATE.format(period=args.period))
            response.raise_for_status()
            await import_omi_records(pool, parse_omi_rows(io.StringIO(response.text), period=args.period))
    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
