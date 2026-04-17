"""Kafka consumer for enriched listings."""

from __future__ import annotations

from datetime import UTC, datetime
import json
from decimal import Decimal
from typing import Any
from uuid import UUID

from estategap_common.broker import KafkaBroker, Message
from estategap_common.models import ScoredListingEvent, ScoringResult, ShapFeatureEvent
from estategap_ml import logger

from ..kafka_publisher import publish_scored_listing
from .comparables import ComparablesFinder
from .db_writer import write_scores
from .inference import _deal_tier, score_listing
from .metrics import SCORER_BATCH_SIZE
from .model_registry import ModelRegistry
from .shap_explainer import ShapExplainer


CONSUMER_GROUP = "estategap.ml-scorer"
INPUT_TOPIC = "enriched-listings"


class KafkaConsumer:
    """Consume enriched listings and emit scored-listing events."""

    def __init__(
        self,
        *,
        config: Any,
        db_pool: Any,
        registry: ModelRegistry,
        broker: KafkaBroker,
        consumer: Any | None = None,
        shap_explainer: ShapExplainer | None = None,
        comparables_finder: ComparablesFinder | None = None,
    ) -> None:
        self._config = config
        self._db_pool = db_pool
        self._registry = registry
        self._broker = broker
        self._consumer = consumer
        self._shap_explainer = shap_explainer
        self._comparables_finder = comparables_finder

    async def consume_loop(self) -> None:
        """Run the scorer consumer loop."""

        owns_consumer = self._consumer is None
        if self._consumer is None:
            self._consumer = await self._broker.create_consumer([INPUT_TOPIC], CONSUMER_GROUP)
        try:
            await self._broker.consume(self._consumer, CONSUMER_GROUP, self.handle_message)
        finally:
            if owns_consumer and self._consumer is not None:
                await self._consumer.stop()
                self._consumer = None

    async def _fetch_row(self, listing_id: UUID) -> dict[str, Any] | None:
        async with self._db_pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT
                    listings.*,
                    ST_Y(location) AS lat,
                    ST_X(location) AS lon
                FROM listings
                WHERE id = $1
                """,
                listing_id,
            )
        return dict(row) if row is not None else None

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

    async def _score_row(self, row: dict[str, Any]) -> Any:
        country = str(row.get("country") or row.get("country_code") or "").lower()
        bundle = self._registry.get(country)
        if bundle is None:
            return await self._heuristic_result(row, confidence="none")
        if getattr(bundle, "confidence", "full") == "insufficient_data":
            return await self._heuristic_result(row, confidence="insufficient_data")

        result = score_listing(
            bundle,
            row,
            shap_explainer=self._shap_explainer,
            mode="batch",
        )
        result.scoring_method = "ml"
        result.model_confidence = getattr(bundle, "confidence", "full")
        if self._comparables_finder is not None:
            result.comparable_ids = [
                comparable_id
                for comparable_id, _ in self._comparables_finder.get_comparables(
                    row,
                    bundle.feature_engineer,
                )
            ]
        return result

    async def handle_message(self, message: Message) -> None:
        try:
            payload = json.loads(message.value)
            listing_id = UUID(str(payload.get("id") or payload.get("listing_id")))
        except Exception as exc:  # noqa: BLE001
            raise ValueError("invalid_scored_listing_payload") from exc

        row = await self._fetch_row(listing_id)
        if row is None:
            logger.warning("scoring_listing_not_found", listing_id=str(listing_id))
            return

        result = await self._score_row(row)
        await write_scores(self._db_pool, [result])
        await publish_scored_listing(self._broker, result)
        SCORER_BATCH_SIZE.labels(country=result.country).observe(1)


__all__ = ["CONSUMER_GROUP", "INPUT_TOPIC", "KafkaConsumer"]
