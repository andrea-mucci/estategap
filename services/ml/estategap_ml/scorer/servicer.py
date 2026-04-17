"""gRPC servicer implementation for ML scoring."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

import grpc
from estategap.v1 import common_pb2, listings_pb2, ml_scoring_pb2, ml_scoring_pb2_grpc
from estategap_common.broker import KafkaBroker
from estategap_common.models import ScoringResult

from ..kafka_publisher import publish_scored_listing
from .comparables import ComparablesFinder
from .db_writer import write_scores
from .inference import _deal_tier, score_listing
from .model_registry import ModelRegistry
from .shap_explainer import ShapExplainer


def _timestamp(value: datetime | None) -> common_pb2.Timestamp:
    millis = int((value.timestamp() if value else 0) * 1000)
    return common_pb2.Timestamp(millis=millis)


def _money(value: Any) -> common_pb2.Money:
    if value is None:
        return common_pb2.Money()
    amount = int(Decimal(str(value)) * 100)
    return common_pb2.Money(amount=amount, currency_code="EUR", eur_amount=amount)


def _listing_status(value: str | None) -> int:
    return {
        "active": listings_pb2.LISTING_STATUS_ACTIVE,
        "sold": listings_pb2.LISTING_STATUS_SOLD,
        "rented": listings_pb2.LISTING_STATUS_RENTED,
        "withdrawn": listings_pb2.LISTING_STATUS_WITHDRAWN,
    }.get(str(value or "").lower(), listings_pb2.LISTING_STATUS_UNSPECIFIED)


def _property_type(row: dict[str, Any]) -> int:
    category = str(row.get("property_category") or "").lower()
    return {
        "residential": listings_pb2.PROPERTY_TYPE_RESIDENTIAL,
        "commercial": listings_pb2.PROPERTY_TYPE_COMMERCIAL,
        "industrial": listings_pb2.PROPERTY_TYPE_INDUSTRIAL,
        "land": listings_pb2.PROPERTY_TYPE_LAND,
    }.get(category, listings_pb2.PROPERTY_TYPE_UNSPECIFIED)


def _listing_proto(row: dict[str, Any]) -> listings_pb2.Listing:
    return listings_pb2.Listing(
        id=str(row["id"]),
        portal_id=str(row.get("portal_id") or ""),
        country_code=str(row.get("country") or row.get("country_code") or "").upper(),
        status=_listing_status(row.get("status")),
        listing_type=listings_pb2.LISTING_TYPE_SALE,
        property_type=_property_type(row),
        price=_money(row.get("asking_price_eur") or row.get("asking_price")),
        area_sqm=float(row.get("built_area_m2") or 0.0),
        location=common_pb2.GeoPoint(
            latitude=float(row.get("lat") or 0.0),
            longitude=float(row.get("lon") or 0.0),
        ),
        created_at=_timestamp(row.get("created_at")),
        updated_at=_timestamp(row.get("updated_at")),
    )


class MLScoringServicer(ml_scoring_pb2_grpc.MLScoringServiceServicer):
    """Async gRPC implementation backed by the scorer runtime."""

    def __init__(
        self,
        *,
        config: Any,
        db_pool: Any,
        registry: ModelRegistry,
        broker: KafkaBroker,
        shap_explainer: ShapExplainer | None = None,
        comparables_finder: ComparablesFinder | None = None,
    ) -> None:
        self._config = config
        self._db_pool = db_pool
        self._registry = registry
        self._broker = broker
        self._shap_explainer = shap_explainer
        self._comparables_finder = comparables_finder

    async def _abort(self, context: grpc.aio.ServicerContext, code: grpc.StatusCode, message: str) -> None:
        await context.abort(code, message)

    async def _fetch_listing(self, listing_id: UUID, country_code: str) -> dict[str, Any] | None:
        async with self._db_pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT
                    listings.*,
                    ST_Y(location) AS lat,
                    ST_X(location) AS lon
                FROM listings
                WHERE id = $1
                  AND country = $2
                """,
                listing_id,
                country_code.upper(),
            )
        return dict(row) if row is not None else None

    async def _fetch_listings(self, listing_ids: list[UUID], country_code: str) -> dict[UUID, dict[str, Any]]:
        async with self._db_pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT
                    listings.*,
                    ST_Y(location) AS lat,
                    ST_X(location) AS lon
                FROM listings
                WHERE id = ANY($1::uuid[])
                  AND country = $2
                """,
                listing_ids,
                country_code.upper(),
            )
        return {row["id"]: dict(row) for row in rows}

    async def _publish_result(self, result: Any) -> None:
        await publish_scored_listing(self._broker, result)

    def _result_proto(self, result: Any) -> ml_scoring_pb2.ScoreListingResponse:
        return ml_scoring_pb2.ScoreListingResponse(
            listing_id=str(result.listing_id),
            deal_score=float(result.deal_score),
            shap_values=[
                ml_scoring_pb2.ShapValue(
                    feature_name=value.feature_name,
                    value=float(value.value),
                    contribution=float(value.contribution),
                    label=value.label,
                )
                for value in result.shap_features
            ],
            model_version=result.model_version,
            estimated_price=float(result.estimated_price),
            asking_price=float(result.asking_price or 0),
            confidence_low=float(result.confidence_low),
            confidence_high=float(result.confidence_high),
            deal_tier=int(result.deal_tier),
            scored_at=result.scored_at.isoformat(),
        )

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
        country_code = str(row.get("country") or row.get("country_code") or "").lower()
        bundle = self._registry.get(country_code)
        if bundle is None:
            return await self._heuristic_result(row, confidence="none")
        if getattr(bundle, "confidence", "full") == "insufficient_data":
            return await self._heuristic_result(row, confidence="insufficient_data")
        result = score_listing(
            bundle,
            row,
            shap_explainer=self._shap_explainer,
            mode="ondemand",
        )
        result.scoring_method = "ml"
        result.model_confidence = getattr(bundle, "confidence", "full")
        if self._comparables_finder is not None:
            result.comparable_ids = [
                listing_id
                for listing_id, _ in self._comparables_finder.get_comparables(
                    row,
                    bundle.feature_engineer,
                )
            ]
        return result

    async def ScoreListing(
        self,
        request: ml_scoring_pb2.ScoreListingRequest,
        context: grpc.aio.ServicerContext,
    ) -> ml_scoring_pb2.ScoreListingResponse:
        try:
            listing_id = UUID(request.listing_id)
        except ValueError:
            await self._abort(context, grpc.StatusCode.INVALID_ARGUMENT, "listing_id must be a UUID")
        country_code = request.country_code.strip().lower()
        if len(country_code) != 2:
            await self._abort(context, grpc.StatusCode.INVALID_ARGUMENT, "country_code must be ISO-3166 alpha2")
        row = await self._fetch_listing(listing_id, country_code)
        if row is None:
            await self._abort(context, grpc.StatusCode.NOT_FOUND, "listing not found")
        try:
            result = await self._score_row(row)
            await write_scores(self._db_pool, [result])
            await self._publish_result(result)
        except LookupError as exc:
            await self._abort(context, grpc.StatusCode.FAILED_PRECONDITION, str(exc))
        except Exception as exc:
            await self._abort(context, grpc.StatusCode.INTERNAL, str(exc))
        return self._result_proto(result)

    async def ScoreBatch(
        self,
        request: ml_scoring_pb2.ScoreBatchRequest,
        context: grpc.aio.ServicerContext,
    ) -> ml_scoring_pb2.ScoreBatchResponse:
        if len(request.listing_ids) > 500:
            await self._abort(context, grpc.StatusCode.RESOURCE_EXHAUSTED, "ScoreBatch max size is 500")
        country_code = request.country_code.strip().lower()
        if len(country_code) != 2:
            await self._abort(context, grpc.StatusCode.INVALID_ARGUMENT, "country_code must be ISO-3166 alpha2")
        try:
            listing_ids = [UUID(value) for value in request.listing_ids]
        except ValueError:
            await self._abort(context, grpc.StatusCode.INVALID_ARGUMENT, "listing_ids must all be UUIDs")
        rows = await self._fetch_listings(listing_ids, country_code)
        if not rows:
            await self._abort(context, grpc.StatusCode.NOT_FOUND, "no requested listings were found")
        try:
            results = [await self._score_row(rows[listing_id]) for listing_id in listing_ids if listing_id in rows]
            await write_scores(self._db_pool, results)
            for result in results:
                await self._publish_result(result)
        except LookupError as exc:
            await self._abort(context, grpc.StatusCode.FAILED_PRECONDITION, str(exc))
        except Exception as exc:
            await self._abort(context, grpc.StatusCode.INTERNAL, str(exc))
        return ml_scoring_pb2.ScoreBatchResponse(scores=[self._result_proto(result) for result in results])

    async def GetComparables(
        self,
        request: ml_scoring_pb2.GetComparablesRequest,
        context: grpc.aio.ServicerContext,
    ) -> ml_scoring_pb2.GetComparablesResponse:
        try:
            listing_id = UUID(request.listing_id)
        except ValueError:
            await self._abort(context, grpc.StatusCode.INVALID_ARGUMENT, "listing_id must be a UUID")
        country_code = request.country_code.strip().lower()
        if len(country_code) != 2:
            await self._abort(context, grpc.StatusCode.INVALID_ARGUMENT, "country_code must be ISO-3166 alpha2")
        row = await self._fetch_listing(listing_id, country_code)
        if row is None:
            await self._abort(context, grpc.StatusCode.NOT_FOUND, "listing not found")
        bundle = self._registry.get(country_code)
        if bundle is None:
            await self._abort(context, grpc.StatusCode.FAILED_PRECONDITION, f"No active model loaded for {country_code}")
        if self._comparables_finder is None:
            return ml_scoring_pb2.GetComparablesResponse()
        comparable_pairs = self._comparables_finder.get_comparables(
            row,
            bundle.feature_engineer,
            limit=max(1, min(request.limit or 5, 10)),
        )
        if not comparable_pairs:
            return ml_scoring_pb2.GetComparablesResponse()
        comparable_rows = await self._fetch_listings([listing_id for listing_id, _ in comparable_pairs], country_code)
        return ml_scoring_pb2.GetComparablesResponse(
            comparables=[
                _listing_proto(comparable_rows[listing_id])
                for listing_id, _ in comparable_pairs
                if listing_id in comparable_rows
            ],
            distances=[distance for _, distance in comparable_pairs if _ in comparable_rows],
        )


__all__ = ["MLScoringServicer"]
