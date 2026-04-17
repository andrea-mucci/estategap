"""Kafka consumer for scrape commands."""

from __future__ import annotations

import asyncio

import redis.asyncio as redis
import structlog
from estategap_common.broker import KafkaBroker, KafkaConfig, Message
from estategap_common.broker.kafka_lag import start_lag_poller

from .config import Config
from .http_client import ParseError, PermanentFailureError
from .metrics import LISTINGS_SCRAPED, SCRAPE_DURATION, SCRAPE_ERRORS
from .models import ScraperCommand
from .quarantine import QuarantineStore
from .spiders import get_spider
from .spiders.fixture_spider import FixtureSpider


LOGGER = structlog.get_logger(__name__)


async def run(config: Config) -> None:
    """Run the Kafka consumer loop."""

    broker = KafkaBroker(
        KafkaConfig(
            brokers=config.kafka_brokers,
            topic_prefix=config.kafka_topic_prefix,
            max_retries=config.kafka_max_retries,
        ),
        service_name="spider-workers",
    )
    consumer = await broker.create_consumer(["scraper-commands"], "estategap.spider-workers")
    lag_task = asyncio.create_task(start_lag_poller(consumer, "estategap.spider-workers"))

    LOGGER.info(
        "consumer_started",
        topic=broker.full_topic_name("scraper-commands"),
        group="estategap.spider-workers",
    )

    try:
        async def handler(message: Message) -> None:
            await process_message(message, broker, config)

        await broker.consume(consumer, "estategap.spider-workers", handler)
    except asyncio.CancelledError:
        LOGGER.info("consumer_cancelled")
        raise
    finally:
        lag_task.cancel()
        await asyncio.gather(lag_task, return_exceptions=True)
        await broker.stop()


async def process_message(message: Message, broker: KafkaBroker, config: Config) -> None:
    """Process a single scrape command message."""

    try:
        command = ScraperCommand.model_validate_json(message.value)
    except Exception as exc:  # noqa: BLE001
        SCRAPE_ERRORS.labels(portal="unknown", country="unknown", error_type="parse_error").inc()
        LOGGER.error("invalid_scraper_command", error=str(exc))
        raise

    if config.estategap_test_mode:
        spider = FixtureSpider(config, country=command.country, portal=command.portal)
    else:
        spider_cls = get_spider(command.country, command.portal)
        if spider_cls is None:
            SCRAPE_ERRORS.labels(
                portal=command.portal,
                country=command.country,
                error_type="unknown_portal",
            ).inc()
            raise LookupError(f"unknown portal {command.portal!r} for country {command.country!r}")
        spider = spider_cls(config)
    spider.search_url = command.search_url

    try:
        if command.mode == "detect_new":
            await _run_detect_new(spider, command, broker, config)
        else:
            await _run_full_scrape(spider, command, broker, config)
    except asyncio.CancelledError:
        raise
    except Exception as exc:  # noqa: BLE001
        error_type = _error_type(exc)
        SCRAPE_ERRORS.labels(
            portal=command.portal,
            country=command.country,
            error_type=error_type,
        ).inc()
        LOGGER.error("scrape_command_failed", error=str(exc), error_type=error_type)
        raise
    finally:
        await spider.close()


async def _run_full_scrape(spider, command: ScraperCommand, broker: KafkaBroker, config: Config) -> None:
    quarantine_redis = redis.from_url(config.redis_url, decode_responses=True)
    quarantine = QuarantineStore(quarantine_redis, config.quarantine_ttl_days)
    try:
        zones = command.zone_filter or ["default"]
        with SCRAPE_DURATION.labels(portal=spider.PORTAL, country=spider.COUNTRY.lower()).time():
            for zone in zones:
                page = 1
                while True:
                    try:
                        listings = await spider.scrape_search_page(zone, page)
                    except PermanentFailureError as exc:
                        await quarantine.add(command.search_url, spider.PORTAL, spider.COUNTRY, str(exc))
                        SCRAPE_ERRORS.labels(
                            portal=spider.PORTAL,
                            country=spider.COUNTRY.lower(),
                            error_type="quarantined",
                        ).inc()
                        break

                    if not listings:
                        break

                    for listing in listings:
                        await _publish_listing(broker, listing)
                        LISTINGS_SCRAPED.labels(
                            portal=spider.PORTAL,
                            country=spider.COUNTRY.lower(),
                        ).inc()
                    page += 1
    finally:
        await quarantine_redis.aclose()


async def _run_detect_new(spider, command: ScraperCommand, broker: KafkaBroker, config: Config) -> None:
    quarantine_redis = redis.from_url(config.redis_url, decode_responses=True)
    quarantine = QuarantineStore(quarantine_redis, config.quarantine_ttl_days)
    try:
        zones = command.zone_filter or ["default"]
        for zone in zones:
            try:
                urls = await spider.detect_new_listings(zone, set())
            except PermanentFailureError as exc:
                await quarantine.add(command.search_url, spider.PORTAL, spider.COUNTRY, str(exc))
                SCRAPE_ERRORS.labels(
                    portal=spider.PORTAL,
                    country=spider.COUNTRY.lower(),
                    error_type="quarantined",
                ).inc()
                continue

            for url in urls:
                try:
                    listing = await spider.scrape_listing_detail(url)
                except PermanentFailureError as exc:
                    await quarantine.add(url, spider.PORTAL, spider.COUNTRY, str(exc))
                    SCRAPE_ERRORS.labels(
                        portal=spider.PORTAL,
                        country=spider.COUNTRY.lower(),
                        error_type="quarantined",
                    ).inc()
                    continue

                if listing is None:
                    continue

                await _publish_listing(broker, listing)
                await spider._mark_seen(spider.redis, zone, {listing.external_id})
                LISTINGS_SCRAPED.labels(
                    portal=spider.PORTAL,
                    country=spider.COUNTRY.lower(),
                ).inc()
    finally:
        await quarantine_redis.aclose()


async def _publish_listing(broker: KafkaBroker, listing) -> None:
    await broker.publish(
        "raw-listings",
        listing.country_code.upper(),
        listing.model_dump_json().encode(),
    )


def _error_type(error: Exception) -> str:
    if isinstance(error, ParseError):
        return "parse_error"
    if isinstance(error, asyncio.TimeoutError):
        return "timeout"
    message = str(error).lower()
    if "403" in message or "429" in message or "captcha" in message:
        return "http_blocked"
    return "unknown"
