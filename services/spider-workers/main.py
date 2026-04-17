import asyncio

import structlog

from estategap_common.logging import configure_logging

from estategap_spiders.config import Config
from estategap_spiders.consumer import run
from estategap_spiders.metrics import start_metrics_server


async def main() -> None:
    config = Config()
    configure_logging(config.log_level, service="spider-workers")
    start_metrics_server(config.metrics_port)
    structlog.get_logger(__name__).info("metrics_server_started", port=config.metrics_port)
    await run(config)


if __name__ == "__main__":
    asyncio.run(main())
