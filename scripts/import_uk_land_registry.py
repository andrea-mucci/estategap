"""Download and import UK Land Registry Price Paid data."""

from __future__ import annotations

import argparse
import asyncio
import csv
import io
import re
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import asyncpg  # type: ignore[import-untyped]
import httpx

COMPLETE_URL = "https://prod.publicdata.landregistry.gov.uk.s3-website-eu-west-1.amazonaws.com/pp-complete.csv"


def normalize_uk_address(address: str, postcode: str | None = None) -> str:
    text = address.lower()
    if postcode:
        text = f"{text} {postcode.lower()}"
    text = re.sub(r"[^a-z0-9]+", " ", text)
    for source, target in {
        " road ": " rd ",
        " street ": " st ",
        " avenue ": " ave ",
        " apartment ": " flat ",
    }.items():
        text = text.replace(source, target)
    return " ".join(text.split())


def parse_price_paid_rows(handle: io.TextIOBase) -> list[tuple[Any, ...]]:
    reader = csv.reader(handle)
    rows: list[tuple[Any, ...]] = []
    for row in reader:
        if len(row) < 16:
            continue
        transaction_uid = row[0].strip('"')
        postcode = row[3].strip('"')
        address = " ".join(part.strip('"') for part in row[7:14] if part.strip('"'))
        rows.append(
            (
                transaction_uid,
                int(row[1].strip('"') or "0"),
                row[2].strip('"'),
                postcode,
                row[4].strip('"') or None,
                row[5].strip('"') or None,
                row[6].strip('"') or None,
                row[7].strip('"') or None,
                row[8].strip('"') or None,
                row[9].strip('"') or None,
                row[10].strip('"') or None,
                row[11].strip('"') or None,
                row[12].strip('"') or None,
                row[13].strip('"') or None,
                normalize_uk_address(address, postcode),
            )
        )
    return rows


async def import_price_paid_records(pool: asyncpg.Pool, records: Iterable[tuple[Any, ...]]) -> None:
    async with pool.acquire() as conn:
        await conn.executemany(
            """
            INSERT INTO uk_price_paid (
                transaction_uid,
                price_gbp,
                date_transfer,
                postcode,
                property_type,
                old_new,
                tenure,
                paon,
                saon,
                street,
                locality,
                town_city,
                district,
                county,
                address_normalized
            ) VALUES (
                $1::uuid,
                $2,
                $3::date,
                $4,
                $5,
                $6,
                $7,
                $8,
                $9,
                $10,
                $11,
                $12,
                $13,
                $14,
                $15
            )
            ON CONFLICT (transaction_uid) DO NOTHING
            """,
            list(records),
        )


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--complete", action="store_true")
    parser.add_argument("--monthly")
    parser.add_argument("--input-file")
    args = parser.parse_args()

    if not args.complete and not args.monthly and not args.input_file:
        raise SystemExit("Provide --complete, --monthly YYYY-MM, or --input-file")

    url = COMPLETE_URL if args.complete else f"https://landregistry.data/{args.monthly}.csv"
    pool = await asyncpg.create_pool(args.database_url, min_size=1, max_size=2)
    try:
        if args.input_file:
            text = Path(args.input_file).read_text(encoding="utf-8")
            await import_price_paid_records(pool, parse_price_paid_rows(io.StringIO(text)))
            return
        async with httpx.AsyncClient(timeout=180.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            await import_price_paid_records(pool, parse_price_paid_rows(io.StringIO(response.text)))
    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
