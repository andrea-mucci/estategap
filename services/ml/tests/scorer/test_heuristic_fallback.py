from __future__ import annotations

from types import SimpleNamespace

import pytest

pytest.importorskip("grpc")

from estategap_ml.scorer.servicer import MLScoringServicer

from tests.scorer_support import build_fake_bundle, make_listing


class _FakeConnection:
    async def fetchval(self, query: str, country_code: str, zone_id):
        del query, country_code, zone_id
        return 2500.0


class _FakePool:
    def acquire(self):
        class _ContextManager:
            async def __aenter__(self):
                return _FakeConnection()

            async def __aexit__(self, exc_type, exc, tb):
                return None

        return _ContextManager()


class _FakeJetStream:
    async def publish(self, subject: str, payload: bytes) -> None:
        del subject, payload
        return None


@pytest.mark.asyncio
async def test_missing_country_bundle_returns_heuristic_result() -> None:
    servicer = MLScoringServicer(
        config=SimpleNamespace(),
        db_pool=_FakePool(),
        registry=SimpleNamespace(get=lambda country: None),
        jetstream=_FakeJetStream(),
    )

    result = await servicer._score_row(make_listing(country="US", built_area_m2=100.0, asking_price_eur=200000.0))

    assert result.scoring_method == "heuristic"
    assert result.model_confidence == "none"
    assert float(result.estimated_price) == pytest.approx(250000.0)


@pytest.mark.asyncio
async def test_insufficient_data_bundle_returns_heuristic_result() -> None:
    bundle = build_fake_bundle(country_code="nl", confidence="insufficient_data")
    servicer = MLScoringServicer(
        config=SimpleNamespace(),
        db_pool=_FakePool(),
        registry=SimpleNamespace(get=lambda country: bundle),
        jetstream=_FakeJetStream(),
    )

    result = await servicer._score_row(make_listing(country="NL", built_area_m2=80.0, asking_price_eur=180000.0))

    assert result.scoring_method == "heuristic"
    assert result.model_confidence == "insufficient_data"
    assert float(result.estimated_price) == pytest.approx(200000.0)
