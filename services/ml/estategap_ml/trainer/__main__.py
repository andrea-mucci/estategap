"""CLI entry point for the ML training pipeline."""

from __future__ import annotations

import argparse
import asyncio

import asyncpg
from estategap_common.models._base import validate_country_code

from estategap_ml import Config, logger
from estategap_ml.nats_publisher import TrainingCompletedEvent, TrainingFailedEvent, publish_completed, publish_failed

from .train import TrainingResult, get_active_countries, run_training, run_transfer_training


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="EstateGap ML training pipeline")
    parser.add_argument("--country", help="single country ISO-3166 alpha2 code")
    parser.add_argument(
        "--countries-all",
        action="store_true",
        help="train all countries ordered by listing count",
    )
    parser.add_argument("--dry-run", action="store_true", help="skip production-side promotion side effects")
    return parser


async def _count_listings(config: Config, country: str) -> int:
    conn = await asyncpg.connect(config.database_url)
    try:
        return int(
            await conn.fetchval(
                """
                SELECT COUNT(*)::INTEGER
                FROM listings
                WHERE LOWER(country) = $1
                """,
                country.lower(),
            )
            or 0
        )
    finally:
        await conn.close()


def _normalize_country(value: str) -> str:
    country = value.strip().upper()
    validate_country_code(country)
    return country.lower()


async def _run_for_country(
    *,
    country: str,
    listing_count: int,
    config: Config,
    dry_run: bool,
    spain_result: TrainingResult | None = None,
) -> TrainingResult:
    if country == config.transfer_base_country.lower() or listing_count >= config.transfer_min_listings:
        return await run_training(country, config, dry_run=dry_run)
    if listing_count < 1000:
        msg = f"{country.upper()} has only {listing_count} listings; at least 1000 are required"
        raise ValueError(msg)
    if spain_result is None:
        msg = "Spain base model unavailable; skipping transfer-learning country."
        raise RuntimeError(msg)
    return await run_transfer_training(
        country,
        spain_booster=spain_result.model,
        config=config,
        dry_run=dry_run,
    )


async def _list_country_counts(config: Config) -> list[tuple[str, int]]:
    conn = await asyncpg.connect(config.database_url)
    try:
        rows = await conn.fetch(
            """
            SELECT LOWER(country) AS country, COUNT(*)::INTEGER AS listing_count
            FROM listings
            GROUP BY country
            ORDER BY CASE WHEN LOWER(country) = 'es' THEN 0 ELSE 1 END, COUNT(*) DESC
            """
        )
    finally:
        await conn.close()
    return [(row["country"], row["listing_count"]) for row in rows]


async def _publish_success(config: Config, result: TrainingResult) -> None:
    await publish_completed(
        TrainingCompletedEvent(
            country_code=result.country,
            model_version_tag=result.version_tag,
            mape_national=result.metrics.mape_national,
            promoted=result.promoted,
            previous_champion_tag=result.previous_champion_tag,
            artifact_path=str(result.onnx_path),
        ),
        config.nats_url,
    )


async def _publish_failure(config: Config, country: str | None, stage: str, exc: Exception) -> None:
    await publish_failed(
        TrainingFailedEvent(
            country_code=country,
            error=str(exc),
            stage=stage,
        ),
        config.nats_url,
    )


async def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()
    if not args.country and not args.countries_all:
        parser.error("Either --country or --countries-all is required")

    config = Config()
    if args.country:
        try:
            country = _normalize_country(args.country)
        except ValueError as exc:
            parser.error(str(exc))
        try:
            listing_count = await _count_listings(config, country)
            if listing_count <= 0:
                raise ValueError(f"No listings found for {country.upper()}")
            spain_result = None
            if country != config.transfer_base_country.lower() and listing_count < config.transfer_min_listings:
                base_count = await _count_listings(config, config.transfer_base_country.lower())
                if base_count >= config.transfer_min_listings:
                    spain_result = await run_training(
                        config.transfer_base_country.lower(),
                        config,
                        dry_run=args.dry_run,
                    )
            result = await _run_for_country(
                country=country,
                listing_count=listing_count,
                config=config,
                dry_run=args.dry_run,
                spain_result=spain_result,
            )
            await _publish_success(config, result)
            return 0
        except Exception as exc:  # pragma: no cover - operational path
            logger.exception("single_country_training_failed", country=country)
            await _publish_failure(config, country, "training", exc)
            return 1

    spain_result: TrainingResult | None = None
    for country, listing_count in await get_active_countries(config, min_listings=1000):
        try:
            result = await _run_for_country(
                country=country,
                listing_count=listing_count,
                config=config,
                dry_run=args.dry_run,
                spain_result=spain_result,
            )
            if country == config.transfer_base_country.lower():
                spain_result = result
            await _publish_success(config, result)
        except Exception as exc:  # pragma: no cover - operational path
            logger.exception("country_training_failed", country=country)
            await _publish_failure(config, country, "training", exc)
            if country == config.transfer_base_country.lower():
                spain_result = None
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
