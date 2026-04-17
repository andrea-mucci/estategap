from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

pytest.importorskip("numpy")
pytest.importorskip("pandas")
pytest.importorskip("sklearn")

import numpy as np
from sklearn.neighbors import NearestNeighbors
from sklearn.preprocessing import StandardScaler

from estategap_ml.scorer.comparables import ComparablesFinder, ZoneIndex

from tests.scorer_support import FakeFeatureEngineer


def _zone_index(listing_ids, vectors, zone_id):
    scaler = StandardScaler().fit(vectors)
    scaled = scaler.transform(vectors)
    nn = NearestNeighbors(n_neighbors=min(5, len(listing_ids)), metric="euclidean", algorithm="ball_tree")
    nn.fit(scaled)
    return ZoneIndex(
        zone_id=zone_id,
        nn=nn,
        scaler=scaler,
        listing_ids=listing_ids,
        built_at=datetime.now(tz=UTC),
    )


def test_knn_returns_5_nearest() -> None:
    zone_id = uuid4()
    listing_ids = [uuid4() for _ in range(20)]
    vectors = np.asarray([[200000 + idx, 80 + idx, 2 + (idx % 3)] for idx in range(20)], dtype=float)
    registry = SimpleNamespace(bundles={"es": SimpleNamespace(feature_engineer=FakeFeatureEngineer())})
    finder = ComparablesFinder(refresh_interval_seconds=3600, registry=registry)
    finder._indices["es"] = {zone_id: _zone_index(listing_ids, vectors, zone_id)}

    listing = {
        "id": listing_ids[0],
        "country": "ES",
        "zone_id": zone_id,
        "asking_price_eur": 200000,
        "built_area_m2": 80,
        "bedrooms": 2,
    }
    results = finder.get_comparables(listing, FakeFeatureEngineer(), limit=5)

    assert len(results) == 5
    assert [distance for _, distance in results] == sorted(distance for _, distance in results)


def test_empty_zone_returns_empty() -> None:
    finder = ComparablesFinder(refresh_interval_seconds=3600, registry=SimpleNamespace(bundles={}))

    assert finder.get_comparables({"id": uuid4(), "country": "ES", "zone_id": uuid4()}, FakeFeatureEngineer()) == []


def test_small_zone_returns_all() -> None:
    zone_id = uuid4()
    listing_ids = [uuid4() for _ in range(3)]
    vectors = np.asarray([[200000 + idx, 80 + idx, 2] for idx in range(3)], dtype=float)
    registry = SimpleNamespace(bundles={"es": SimpleNamespace(feature_engineer=FakeFeatureEngineer())})
    finder = ComparablesFinder(refresh_interval_seconds=3600, registry=registry)
    finder._indices["es"] = {zone_id: _zone_index(listing_ids, vectors, zone_id)}

    results = finder.get_comparables(
        {
            "id": listing_ids[0],
            "country": "ES",
            "zone_id": zone_id,
            "asking_price_eur": 200000,
            "built_area_m2": 80,
            "bedrooms": 2,
        },
        FakeFeatureEngineer(),
        limit=5,
    )

    assert len(results) == 2


def test_distance_ordering() -> None:
    zone_id = uuid4()
    listing_ids = [uuid4() for _ in range(6)]
    vectors = np.asarray([[200000 + idx * 1000, 80 + idx, 2 + idx] for idx in range(6)], dtype=float)
    registry = SimpleNamespace(bundles={"es": SimpleNamespace(feature_engineer=FakeFeatureEngineer())})
    finder = ComparablesFinder(refresh_interval_seconds=3600, registry=registry)
    finder._indices["es"] = {zone_id: _zone_index(listing_ids, vectors, zone_id)}

    results = finder.get_comparables(
        {
            "id": listing_ids[0],
            "country": "ES",
            "zone_id": zone_id,
            "asking_price_eur": 200000,
            "built_area_m2": 80,
            "bedrooms": 2,
        },
        FakeFeatureEngineer(),
        limit=5,
    )

    assert results[0][1] <= results[-1][1]
