"""JetStream consumer for enriched listings."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
import json
from decimal import Decimal
from typing import Any
from uuid import UUID

from estategap_common.models import ScoredListingEvent, ScoringResult, ShapFeatureEvent
from estategap_ml import logger

from .comparables import ComparablesFinder
from .db_writer import write_scores
from .inference import _deal_tier, score_listing
from .metrics import SCORER_BATCH_SIZE
from .model_registry import ModelRegistry
from .shap_explainer import ShapExplainer


class NatsConsumer:
    """Consume enriched listings and flush micro-batches through the scorer."""

    def __init__(
        self,
        *,
        config: Any,
        db_pool: Any,
        registry: ModelRegistry,
        jetstream: Any,
        shap_explainer: ShapExplainer | None = None,
        comparables_finder: ComparablesFinder | None = None,
    ) -> None:
        self._config = config
        self._db_pool = db_pool
        self._registry = registry
        self._jetstream = jetstream
        self._shap_explainer = shap_explainer
        self._comparables_finder = comparables_finder
        self._queue: asyncio.Queue[Any] = asyncio.Queue()
        self._subscribed = False

    async def _ensure_subscription(self) -> None:
        if self._subscribed:
            return
        try:
            from nats.js.api import AckPolicy, ConsumerConfig, DeliverPolicy
        except ModuleNotFoundError:  # pragma: no cover - runtime dependency
            await self._jetstream.subscribe("enriched.listings", cb=self._enqueue)
        else:
            await self._jetstream.subscribe(
                "enriched.listings",
                durable="scorer-group",
                config=ConsumerConfig(
                    ack_policy=AckPolicy.EXPLICIT,
                    max_ack_pending=200,
                    deliver_policy=DeliverPolicy.NEW,
                ),
                cb=self._enqueue,
            )
        self._subscribed = True

    async def _enqueue(self, msg: Any) -> None:
        await self._queue.put(msg)

    async def consume_loop(self) -> None:
        """Subscribe once, then flush batches on size or timeout."""

        await self._ensure_subscription()
        while True:
            batch: list[Any] = []
            try:
                first = await asyncio.wait_for(
                    self._queue.get(),
                    timeout=self._config.scorer_batch_flush_seconds,
                )
            except TimeoutError:
                continue
            batch.append(first)
            deadline = asyncio.get_running_loop().time() + self._config.scorer_batch_flush_seconds
            while len(batch) < self._config.scorer_batch_size:
                timeout = deadline - asyncio.get_running_loop().time()
                if timeout <= 0:
                    break
                try:
                    batch.append(await asyncio.wait_for(self._queue.get(), timeout=timeout))
                except TimeoutError:
                    break
            await self._process_batch(batch)

    async def _fetch_rows(self, listing_ids: list[UUID]) -> dict[UUID, dict[str, Any]]:
        async with self._db_pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT
                    listings.*,
                    ST_Y(location) AS lat,
                    ST_X(location) AS lon
                FROM listings
                WHERE id = ANY($1::uuid[])
                """,
                listing_ids,
            )
        return {row["id"]: dict(row) for row in rows}

    async def _term(self, msg: Any) -> None:
        if hasattr(msg, "term"):
            await msg.term()
        elif hasattr(msg, "ack"):
            await msg.ack()

    async def _nak(self, msg: Any) -> None:
        if hasattr(msg, "nak"):
            try:
                await msg.nak(delay=30)
            except TypeError:
                await msg.nak()
        elif hasattr(msg, "ack"):
            await msg.ack()

    def _delivery_attempts(self, msg: Any) -> int:
        metadata = getattr(msg, "metadata", None)
        delivered = getattr(metadata, "num_delivered", None)
        if callable(delivered):
            delivered = delivered()
        return int(delivered or 1)

    async def _retry_or_term(self, msg: Any) -> None:
        if self._delivery_attempts(msg) >= 3:
            await self._term(msg)
            return
        await self._nak(msg)

    async def _zone_median_price(self, row: dict[str, Any]) -> Decimal | None:
        zone_id = row.get("zone_id")
        country_code = str(row.get("country") or row.get("country_code") or "").upper()
        if zone_id is not None:
            async with self._db_pool.acquire() as conn:
                median = await conn.fetchval(
                    """
                    SELECT PERCENTILE_CONT(0.5) WITHIN GROUP (
                        ORDER BY COALESCE(price_per_m2_eur, asking_price_eur / NULLIF(built_area_m2, 0))
                    )
                    FROM listings
                    WHERE country = $1
                      AND zone_id = $2
                      AND built_area_m2 > 0
                    """,
                    country_code,
                    zone_id,
                )
            if median is not None:
                return Decimal(str(median)).quantize(Decimal("0.01"))
        built_area_m2 = Decimal(str(row.get("built_area_m2") or 0))
        asking_price = Decimal(str(row.get("asking_price_eur") or row.get("asking_price") or 0))
        if built_area_m2 > 0 and asking_price > 0:
            return (asking_price / built_area_m2).quantize(Decimal("0.01"))
        return None

    async def _heuristic_result(self, row: dict[str, Any], *, confidence: str) -> ScoringResult:
        median_price_m2 = await self._zone_median_price(row)
        built_area_m2 = Decimal(str(row.get("built_area_m2") or 0)).quantize(Decimal("0.01"))
        asking_price = Decimal(str(row.get("asking_price_eur") or row.get("asking_price") or 0)).quantize(
            Decimal("0.01")
        )
        estimated_price = asking_price
        if median_price_m2 is not None and built_area_m2 > 0:
            estimated_price = (median_price_m2 * built_area_m2).quantize(Decimal("0.01"))
        if estimated_price == 0:
            deal_score = Decimal("0.00")
        else:
            deal_score = ((estimated_price - asking_price) / estimated_price * Decimal("100")).quantize(
                Decimal("0.01")
            )
        band = max(estimated_price * Decimal("0.10"), Decimal("1.00")).quantize(Decimal("0.01"))
        return ScoringResult(
            listing_id=row["id"],
            country=str(row.get("country") or row.get("country_code") or "").lower(),
            estimated_price=estimated_price,
            asking_price=asking_price,
            deal_score=deal_score,
            deal_tier=_deal_tier(deal_score),
            confidence_low=max(Decimal("0.00"), estimated_price - band).quantize(Decimal("0.01")),
            confidence_high=(estimated_price + band).quantize(Decimal("0.01")),
            shap_features=[],
            comparable_ids=[],
            model_version=str(row.get("model_version") or "heuristic"),
            scoring_method="heuristic",
            model_confidence=confidence,
            scored_at=datetime.now(tz=UTC),
        )

    def _event(self, result: Any) -> ScoredListingEvent:
        return ScoredListingEvent(
            listing_id=result.listing_id,
            country_code=result.country.upper(),
            estimated_price_eur=result.estimated_price,
            deal_score=result.deal_score,
            deal_tier=result.deal_tier,
            confidence_low_eur=result.confidence_low,
            confidence_high_eur=result.confidence_high,
            model_version=result.model_version,
            scoring_method=result.scoring_method,
            model_confidence=result.model_confidence,
            scored_at=result.scored_at,
            shap_features=[
                ShapFeatureEvent(
                    feature=value.feature_name,
                    value=value.value,
                    shap_value=value.contribution,
                    label=value.label,
                )
                for value in result.shap_features
            ],
        )

    async def _process_batch(self, batch: list[Any]) -> None:
        parsed: list[tuple[Any, UUID]] = []
        for msg in batch:
            try:
                payload = json.loads(msg.data.decode("utf-8"))
                parsed.append((msg, UUID(str(payload.get("id") or payload.get("listing_id")))))
            except Exception:
                await self._term(msg)
        if not parsed:
            return

        try:
            rows = await self._fetch_rows([listing_id for _, listing_id in parsed])
        except Exception as exc:
            logger.exception("scoring_batch_fetch_failed", error=str(exc))
            for msg, _ in parsed:
                await self._retry_or_term(msg)
            return
        results = []
        ack_messages: list[Any] = []
        for msg, listing_id in parsed:
            row = rows.get(listing_id)
            if row is None:
                await self._term(msg)
                continue
            country = str(row.get("country") or row.get("country_code") or "").lower()
            bundle = self._registry.get(country)
            try:
                if bundle is None:
                    result = await self._heuristic_result(row, confidence="none")
                elif getattr(bundle, "confidence", "full") == "insufficient_data":
                    result = await self._heuristic_result(row, confidence="insufficient_data")
                else:
                    result = score_listing(
                        bundle,
                        row,
                        shap_explainer=self._shap_explainer,
                        mode="batch",
                    )
                    result.scoring_method = "ml"
                    result.model_confidence = getattr(bundle, "confidence", "full")
                if self._comparables_finder is not None and result.scoring_method == "ml":
                    result.comparable_ids = [
                        comparable_id
                        for comparable_id, _ in self._comparables_finder.get_comparables(
                            row,
                            bundle.feature_engineer,
                        )
                    ]
            except Exception as exc:
                logger.exception("scoring_batch_listing_failed", listing_id=str(listing_id), error=str(exc))
                await self._retry_or_term(msg)
                continue
            results.append(result)
            ack_messages.append(msg)

        if not results:
            return

        try:
            await write_scores(self._db_pool, results)
            counts: dict[str, int] = {}
            for result in results:
                counts[result.country] = counts.get(result.country, 0) + 1
                await self._jetstream.publish("scored.listings", self._event(result).model_dump_json().encode("utf-8"))
            for country, count in counts.items():
                SCORER_BATCH_SIZE.labels(country=country).observe(count)
            for msg in ack_messages:
                await msg.ack()
        except Exception as exc:
            logger.exception("scoring_batch_failed", error=str(exc))
            for msg in ack_messages:
                await self._retry_or_term(msg)


__all__ = ["NatsConsumer"]
