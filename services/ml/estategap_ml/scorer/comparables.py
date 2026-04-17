"""Comparable-listing retrieval via per-zone KNN indices."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import numpy as np
import pandas as pd
from sklearn.neighbors import NearestNeighbors
from sklearn.preprocessing import StandardScaler

from .metrics import SCORER_COMPARABLES_CACHE_HIT_RATIO


@dataclass(slots=True)
class ZoneIndex:
    """One KNN index for a specific zone."""

    zone_id: UUID
    nn: NearestNeighbors
    scaler: StandardScaler
    listing_ids: list[UUID]
    built_at: datetime


class ComparablesFinder:
    """Maintain warm comparable indices for active zones."""

    def __init__(self, *, refresh_interval_seconds: int, registry: Any) -> None:
        self._refresh_interval_seconds = refresh_interval_seconds
        self._registry = registry
        self._indices: dict[str, dict[UUID, ZoneIndex]] = {}
        self._requests = 0
        self._hits = 0

    async def refresh_zone_indices(self, db_pool: Any, country_code: str | None = None) -> None:
        """Rebuild zone indices from active listings."""

        countries = [country_code.lower()] if country_code else sorted(self._registry.bundles)
        async with db_pool.acquire() as conn:
            for country in countries:
                bundle = self._registry.get(country)
                if bundle is None:
                    continue
                rows = await conn.fetch(
                    """
                    SELECT
                        listings.*,
                        ST_Y(location) AS lat,
                        ST_X(location) AS lon
                    FROM listings
                    WHERE status = 'active'
                      AND zone_id IS NOT NULL
                      AND country = $1
                    """,
                    country.upper(),
                )
                if not rows:
                    self._indices[country] = {}
                    continue
                frames = [dict(row) for row in rows]
                matrix = bundle.feature_engineer.transform(pd.DataFrame(frames))
                grouped: dict[UUID, list[tuple[UUID, np.ndarray]]] = {}
                for row, vector in zip(frames, matrix, strict=False):
                    grouped.setdefault(row["zone_id"], []).append((row["id"], np.asarray(vector, dtype=float)))
                zone_indices: dict[UUID, ZoneIndex] = {}
                for zone_id, entries in grouped.items():
                    listing_ids = [listing_id for listing_id, _ in entries]
                    values = np.vstack([value for _, value in entries])
                    scaler = StandardScaler().fit(values)
                    scaled = scaler.transform(values)
                    nn = NearestNeighbors(
                        n_neighbors=min(5, len(entries)),
                        metric="euclidean",
                        algorithm="ball_tree",
                    )
                    nn.fit(scaled)
                    zone_indices[zone_id] = ZoneIndex(
                        zone_id=zone_id,
                        nn=nn,
                        scaler=scaler,
                        listing_ids=listing_ids,
                        built_at=datetime.now(tz=UTC),
                    )
                self._indices[country] = zone_indices

    async def refresh_loop(self, db_pool: Any) -> None:
        """Refresh indices forever on the configured cadence."""

        while True:
            await self.refresh_zone_indices(db_pool)
            await asyncio.sleep(self._refresh_interval_seconds)

    def get_comparables(
        self,
        listing_row: Any,
        feature_engineer: Any,
        *,
        limit: int = 5,
    ) -> list[tuple[UUID, float]]:
        """Return nearest listing ids and distances for one listing."""

        row = dict(listing_row.items()) if hasattr(listing_row, "items") else dict(listing_row)
        country = str(row.get("country") or row.get("country_code") or "").lower()
        zone_id = row.get("zone_id")
        self._requests += 1
        zone_index = self._indices.get(country, {}).get(zone_id)
        if zone_index is None:
            SCORER_COMPARABLES_CACHE_HIT_RATIO.set(self._hits / self._requests if self._requests else 0.0)
            return []

        self._hits += 1
        SCORER_COMPARABLES_CACHE_HIT_RATIO.set(self._hits / self._requests if self._requests else 0.0)
        vector = feature_engineer.transform(pd.DataFrame([row]))
        scaled = zone_index.scaler.transform(vector)
        neighbour_count = min(limit + 1, len(zone_index.listing_ids))
        distances, indices = zone_index.nn.kneighbors(scaled, n_neighbors=neighbour_count)
        listing_id = row.get("id")
        results: list[tuple[UUID, float]] = []
        for distance, index in zip(distances[0], indices[0], strict=False):
            candidate = zone_index.listing_ids[int(index)]
            if candidate == listing_id:
                continue
            results.append((candidate, float(distance)))
            if len(results) >= limit:
                break
        return results


__all__ = ["ComparablesFinder", "ZoneIndex"]
