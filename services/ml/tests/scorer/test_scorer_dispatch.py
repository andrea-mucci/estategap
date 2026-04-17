from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import json

import pytest

pytest.importorskip("grpc")

from estategap_ml.scorer.model_registry import _materialize_artifacts
from estategap_ml.scorer.servicer import MLScoringServicer

from tests.scorer_support import build_fake_bundle, make_listing


class _FakePool:
    def acquire(self):
        class _ContextManager:
            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return None

        return _ContextManager()


class _FakeJetStream:
    async def publish(self, subject: str, payload: bytes) -> None:
        json.loads(payload.decode("utf-8"))
        assert subject == "scored.listings"


def test_country_scoped_artifact_paths_expand_expected_sidecars(monkeypatch: pytest.MonkeyPatch) -> None:
    downloaded: list[tuple[str, str]] = []

    def fake_download(s3_client, bucket: str, key: str, target: Path) -> Path:
        downloaded.append((bucket, key))
        return target

    monkeypatch.setattr("estategap_ml.scorer.model_registry._download_s3_object", fake_download)

    for country in ["es", "it", "fr", "gb", "us", "nl"]:
        _materialize_artifacts(
            version_tag=f"{country}_national_v1",
            artifact_path=f"s3://ml-models/{country}/champion/model.onnx",
            bucket="ml-models",
            s3_client=object(),
        )

    expected_keys = {
        "es/champion/model.onnx",
        "it/champion/model.onnx",
        "fr/champion/model.onnx",
        "gb/champion/model.onnx",
        "us/champion/model.onnx",
        "nl/champion/model.onnx",
    }
    assert expected_keys.issubset({key for _, key in downloaded})


@pytest.mark.asyncio
@pytest.mark.parametrize("country", ["ES", "IT", "FR", "GB", "US", "NL"])
async def test_score_row_dispatches_to_country_bundle(country: str) -> None:
    bundles = {
        code: build_fake_bundle(country_code=code, version_tag=f"{code}_national_v1", confidence="transfer")
        for code in ["es", "it", "fr", "gb", "us", "nl"]
    }
    registry = SimpleNamespace(get=lambda code: bundles[code])
    servicer = MLScoringServicer(
        config=SimpleNamespace(),
        db_pool=_FakePool(),
        registry=registry,
        jetstream=_FakeJetStream(),
    )

    result = await servicer._score_row(make_listing(country=country))

    assert result.scoring_method == "ml"
    assert result.model_confidence == "transfer"
    assert result.model_version == f"{country.lower()}_national_v1"
