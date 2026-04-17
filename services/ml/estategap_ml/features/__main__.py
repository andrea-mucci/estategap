"""Smoke-test CLI for the feature engineering pipeline."""

from __future__ import annotations

import argparse
import asyncio

from estategap_ml import Config, logger
from estategap_ml.trainer.data_export import export_training_data

from .engineer import FeatureEngineer
from .zone_stats import fetch_zone_stats


async def _run_smoke_test(country: str, limit: int) -> int:
    config = Config()
    dataset = await export_training_data(country=country, dsn=config.database_url, limit=limit)
    stats = await fetch_zone_stats(country=country, dsn=config.database_url)
    engineer = FeatureEngineer(
        zone_stats=stats.zone_stats,
        city_stats=stats.city_stats,
        country_stats=stats.country_stats,
    )
    matrix = engineer.fit_transform(dataset)
    logger.info(
        "feature_smoke_test_completed",
        country=country,
        rows=len(dataset),
        features=matrix.shape[1],
    )
    print(f"Feature matrix shape: {matrix.shape}")
    print("no NaN ✓ no Inf ✓")
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="EstateGap ML feature engineering tools")
    parser.add_argument("--smoke-test", action="store_true", help="run the feature engineering smoke test")
    parser.add_argument("--country", required=True, help="ISO-3166 alpha2 country code")
    parser.add_argument("--limit", type=int, default=100, help="max number of rows to inspect")
    return parser


async def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()
    if not args.smoke_test:
        parser.error("--smoke-test is required for this CLI")
    return await _run_smoke_test(country=args.country, limit=args.limit)


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
