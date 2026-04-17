from __future__ import annotations

import sys
from pathlib import Path

import pytest

pytest.importorskip("geopandas")

REPO_ROOT = Path(__file__).resolve().parents[4]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.import_gadm_zones import import_gadm_records, load_gadm_records


@pytest.mark.asyncio
async def test_import_gadm_geojson_is_idempotent(asyncpg_pool) -> None:
    fixture = Path(__file__).resolve().parent / "fixtures" / "gadm_fr_sample.geojson"
    records = load_gadm_records("FR", fixture)

    await import_gadm_records(asyncpg_pool, records)
    await import_gadm_records(asyncpg_pool, records)

    row = await asyncpg_pool.fetchrow(
        """
        SELECT COUNT(*) AS total
        FROM zones
        WHERE country_code = 'FR' AND level = 1
        """
    )

    assert int(row["total"]) == 3

