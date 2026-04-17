"""Download and import France DVF transaction data."""

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


DVF_URL_TEMPLATE = "https://files.data.gouv.fr/geo-dvf/latest/csv/{year}/full.csv.gz"


def parse_dvf_rows(handle: io.TextIOBase) -> list[tuple[Any, ...]]:
    reader = csv.DictReader(handle)
    rows: list[tuple[Any, ...]] = []
    for row in reader:
        valeur = row.get("valeur_fonciere")
        date_mutation = row.get("date_mutation")
        if not valeur or not date_mutation:
            continue
        rows.append(
            (
                date_mutation,
                float(str(valeur).replace(",", ".")),
                row.get("type_local") or None,
                float(str(row["surface_reelle_bati"]).replace(",", "."))
                if row.get("surface_reelle_bati")
                else None,
                row.get("adresse_numero") or None,
                row.get("adresse_nom_voie") or None,
                row.get("code_postal") or None,
                row.get("nom_commune") or row.get("commune") or None,
                None,
            )
        )
    return rows


async def import_dvf_records(pool: asyncpg.Pool, records: Iterable[tuple[Any, ...]]) -> None:
    async with pool.acquire() as conn:
        await conn.executemany(
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
            ON CONFLICT (date_mutation, adresse_numero, adresse_nom_voie, valeur_fonciere) DO NOTHING
            """,
            list(records),
        )


async def download_year(client: httpx.AsyncClient, year: int) -> str:
    response = await client.get(DVF_URL_TEMPLATE.format(year=year))
    response.raise_for_status()
    return response.text


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--year-from", type=int, required=True)
    parser.add_argument("--year-to", type=int, required=True)
    parser.add_argument("--input-file")
    args = parser.parse_args()

    pool = await asyncpg.create_pool(args.database_url, min_size=1, max_size=2)
    try:
        if args.input_file:
            text = Path(args.input_file).read_text(encoding="utf-8")
            await import_dvf_records(pool, parse_dvf_rows(io.StringIO(text)))
            return
        async with httpx.AsyncClient(timeout=120.0) as client:
            for year in range(args.year_from, args.year_to + 1):
                text = await download_year(client, year)
                await import_dvf_records(pool, parse_dvf_rows(io.StringIO(text)))
    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
