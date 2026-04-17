"""CLI entry point for the ML training pipeline."""

from __future__ import annotations

import argparse
import asyncio

import asyncpg

from estategap_ml import Config, logger
from estategap_ml.nats_publisher import TrainingCompletedEvent, TrainingFailedEvent, publish_completed, publish_failed

from .train import TrainingResult, run_training, run_transfer_training


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
            result = await run_training(args.country.lower(), config, dry_run=args.dry_run)
            await _publish_success(config, result)
            return 0
        except Exception as exc:  # pragma: no cover - operational path
            logger.exception("single_country_training_failed", country=args.country.lower())
            await _publish_failure(config, args.country.lower(), "training", exc)
            return 1

    spain_result: TrainingResult | None = None
    for country, listing_count in await _list_country_counts(config):
        try:
            if country == "es" or listing_count >= config.min_listings_per_country:
                result = await run_training(country, config, dry_run=args.dry_run)
                if country == "es":
                    spain_result = result
            else:
                if spain_result is None:
                    await _publish_failure(
                        config,
                        country,
                        "training",
                        RuntimeError("Spain base model unavailable; skipping transfer-learning country."),
                    )
                    continue
                result = await run_transfer_training(
                    country,
                    spain_booster=spain_result.model,
                    feature_engineer=spain_result.feature_engineer,
                    config=config,
                    dry_run=args.dry_run,
                )
            await _publish_success(config, result)
        except Exception as exc:  # pragma: no cover - operational path
            logger.exception("country_training_failed", country=country)
            await _publish_failure(config, country, "training", exc)
            if country == "es":
                spain_result = None
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
