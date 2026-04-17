import asyncio

import structlog

from estategap_common.logging import configure_logging
from estategap_common.s3client import S3Client, S3HealthCheckError

from estategap_spiders.config import Config
from estategap_spiders.consumer import run
from estategap_spiders.metrics import start_metrics_server


async def main() -> None:
    config = Config()
    configure_logging(config.log_level, service="spider-workers")
    start_metrics_server(config.metrics_port)
    structlog.get_logger(__name__).info("metrics_server_started", port=config.metrics_port)
    async with S3Client(config.to_s3_config()) as s3:
        try:
            await s3.health_check([
                s3.bucket_name("listing-photos"),
                s3.bucket_name(config.fixture_s3_bucket),
            ])
        except S3HealthCheckError as exc:
            structlog.get_logger(__name__).error("s3_health_check_failed", error=str(exc))
            raise SystemExit(1) from exc
    await run(config)


if __name__ == "__main__":
    asyncio.run(main())
