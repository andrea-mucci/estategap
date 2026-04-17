from __future__ import annotations

import asyncio
import json
from time import perf_counter
from types import SimpleNamespace
from uuid import uuid4

import pytest

pytest.importorskip("asyncpg")
pytest.importorskip("grpc")
pytest.importorskip("testcontainers")

import asyncpg
import grpc
from estategap.v1 import ml_scoring_pb2, ml_scoring_pb2_grpc
from testcontainers.postgres import PostgresContainer

from estategap_ml.scorer.comparables import ComparablesFinder
from estategap_ml.scorer.model_registry import ModelRegistry
from estategap_ml.scorer.servicer import MLScoringServicer

from tests.scorer_support import asyncpg_dsn, build_fake_bundle, make_listing, prepare_scorer_database, seed_model_version


class FakeJetStream:
    def __init__(self) -> None:
        self.published: list[dict[str, object]] = []

    async def publish(self, subject: str, payload: bytes) -> None:
        self.published.append({"subject": subject, "payload": json.loads(payload.decode("utf-8"))})


async def _serve(servicer: MLScoringServicer) -> tuple[grpc.aio.Server, int]:
    server = grpc.aio.server()
    ml_scoring_pb2_grpc.add_MLScoringServiceServicer_to_server(servicer, server)
    port = server.add_insecure_port("127.0.0.1:0")
    await server.start()
    return server, port


async def _channel_stub(port: int):
    channel = grpc.aio.insecure_channel(f"127.0.0.1:{port}")
    await channel.channel_ready()
    return channel, ml_scoring_pb2_grpc.MLScoringServiceStub(channel)


@pytest.mark.asyncio
async def test_score_listing_and_batch_paths() -> None:
    with PostgresContainer("postgis/postgis:16-3.4") as postgres:
        dsn = asyncpg_dsn(postgres.get_connection_url())
        listings = [make_listing(id=uuid4()) for _ in range(100)]
        await prepare_scorer_database(dsn, listings)
        db_pool = await asyncpg.create_pool(dsn)
        try:
            jetstream = FakeJetStream()
            bundle = build_fake_bundle()
            registry = SimpleNamespace(get=lambda country: bundle)
            servicer = MLScoringServicer(
                config=SimpleNamespace(),
                db_pool=db_pool,
                registry=registry,
                jetstream=jetstream,
            )
            server, port = await _serve(servicer)
            channel, stub = await _channel_stub(port)
            try:
                started = perf_counter()
                response = await stub.ScoreListing(
                    ml_scoring_pb2.ScoreListingRequest(
                        listing_id=str(listings[0]["id"]),
                        country_code="es",
                    )
                )
                assert perf_counter() - started < 0.1
                assert response.listing_id == str(listings[0]["id"])
                assert response.estimated_price == pytest.approx(245000.0)
                assert response.confidence_low == pytest.approx(210000.0)
                assert response.confidence_high == pytest.approx(280000.0)
                assert response.deal_tier == 1
                batch_started = perf_counter()
                batch = await stub.ScoreBatch(
                    ml_scoring_pb2.ScoreBatchRequest(
                        listing_ids=[str(item["id"]) for item in listings],
                        country_code="es",
                    )
                )
                assert perf_counter() - batch_started < 3.0
                assert len(batch.scores) == 100
                with pytest.raises(grpc.aio.AioRpcError) as excinfo:
                    await stub.ScoreListing(
                        ml_scoring_pb2.ScoreListingRequest(
                            listing_id=str(uuid4()),
                            country_code="es",
                        )
                    )
                assert excinfo.value.code() == grpc.StatusCode.NOT_FOUND
            finally:
                await channel.close()
                await server.stop(grace=0)
        finally:
            await db_pool.close()


@pytest.mark.asyncio
async def test_get_comparables_warm_and_cold_cache() -> None:
    with PostgresContainer("postgis/postgis:16-3.4") as postgres:
        dsn = asyncpg_dsn(postgres.get_connection_url())
        zone_id = uuid4()
        listings = [
            make_listing(
                id=uuid4(),
                zone_id=zone_id,
                asking_price_eur=200000 + idx * 1000,
                built_area_m2=80 + idx,
                bedrooms=2 + (idx % 2),
            )
            for idx in range(10)
        ]
        await prepare_scorer_database(dsn, listings)
        db_pool = await asyncpg.create_pool(dsn)
        try:
            bundle = build_fake_bundle()
            registry = SimpleNamespace(bundles={"es": bundle}, get=lambda country: bundle)
            jetstream = FakeJetStream()
            warm_finder = ComparablesFinder(refresh_interval_seconds=3600, registry=registry)
            await warm_finder.refresh_zone_indices(db_pool)
            warm_servicer = MLScoringServicer(
                config=SimpleNamespace(),
                db_pool=db_pool,
                registry=registry,
                jetstream=jetstream,
                comparables_finder=warm_finder,
            )
            server, port = await _serve(warm_servicer)
            channel, stub = await _channel_stub(port)
            try:
                response = await stub.GetComparables(
                    ml_scoring_pb2.GetComparablesRequest(
                        listing_id=str(listings[0]["id"]),
                        country_code="es",
                        limit=5,
                    )
                )
                assert len(response.comparables) == 5
                assert len(response.distances) == 5
                assert list(response.distances) == sorted(response.distances)
            finally:
                await channel.close()
                await server.stop(grace=0)

            cold_finder = ComparablesFinder(refresh_interval_seconds=3600, registry=registry)
            cold_servicer = MLScoringServicer(
                config=SimpleNamespace(),
                db_pool=db_pool,
                registry=registry,
                jetstream=jetstream,
                comparables_finder=cold_finder,
            )
            cold_server, cold_port = await _serve(cold_servicer)
            cold_channel, cold_stub = await _channel_stub(cold_port)
            try:
                response = await cold_stub.GetComparables(
                    ml_scoring_pb2.GetComparablesRequest(
                        listing_id=str(listings[0]["id"]),
                        country_code="es",
                        limit=5,
                    )
                )
                assert len(response.comparables) == 0
                assert len(response.distances) == 0
            finally:
                await cold_channel.close()
                await cold_server.stop(grace=0)
        finally:
            await db_pool.close()


@pytest.mark.asyncio
async def test_hot_reload_within_60s_and_serving_during_reload(monkeypatch) -> None:
    with PostgresContainer("postgis/postgis:16-3.4") as postgres:
        dsn = asyncpg_dsn(postgres.get_connection_url())
        listing = make_listing(id=uuid4())
        await prepare_scorer_database(dsn, [listing], include_model_versions=True)
        await seed_model_version(
            dsn,
            country_code="es",
            version_tag="es_national_v1",
            artifact_path="/tmp/es_national_v1.onnx",
            feature_names=["asking_price_eur", "built_area_m2", "bedrooms"],
        )
        db_pool = await asyncpg.create_pool(dsn)
        try:
            bundles = {
                "es_national_v1": build_fake_bundle(version_tag="es_national_v1", point=245000.0),
                "es_national_v2": build_fake_bundle(version_tag="es_national_v2", point=260000.0),
            }

            async def promote_new_version() -> None:
                async with db_pool.acquire() as conn:
                    await conn.execute("UPDATE model_versions SET status = 'retired' WHERE country_code = 'ES'")
                    await conn.execute(
                        """
                        INSERT INTO model_versions (country_code, version_tag, artifact_path, feature_names, status, trained_at, created_at)
                        VALUES ('ES', 'es_national_v2', '/tmp/es_national_v2.onnx', '[]'::jsonb, 'active', NOW(), NOW())
                        """
                    )

            def fake_download_bundle(version_tag: str, artifact_path: str, bucket: str, **kwargs: object):
                if version_tag == "es_national_v2":
                    import time

                    time.sleep(0.2)
                return bundles[version_tag]

            monkeypatch.setattr("estategap_ml.scorer.model_registry.download_bundle", fake_download_bundle)
            registry = ModelRegistry(bucket="estategap-models", s3_client=object(), poll_interval_seconds=0.05)
            await registry.load_active_models(db_pool)
            assert registry.get("es").version_tag == "es_national_v1"

            poll_task = asyncio.create_task(registry.poll_loop(db_pool))
            await promote_new_version()

            bundle_before_swap = registry.get("es")
            assert bundle_before_swap is not None

            jetstream = FakeJetStream()
            servicer = MLScoringServicer(
                config=SimpleNamespace(),
                db_pool=db_pool,
                registry=registry,
                jetstream=jetstream,
            )
            server, port = await _serve(servicer)
            channel, stub = await _channel_stub(port)
            try:
                response = await stub.ScoreListing(
                    ml_scoring_pb2.ScoreListingRequest(
                        listing_id=str(listing["id"]),
                        country_code="es",
                    )
                )
                assert response.model_version == "es_national_v1"
                for _ in range(40):
                    if registry.get("es") and registry.get("es").version_tag == "es_national_v2":
                        break
                    await asyncio.sleep(0.05)
                assert registry.get("es").version_tag == "es_national_v2"
            finally:
                poll_task.cancel()
                await asyncio.gather(poll_task, return_exceptions=True)
                await channel.close()
                await server.stop(grace=0)
        finally:
            await db_pool.close()
