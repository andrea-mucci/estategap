"""NATS JetStream consumer for scrape commands."""

from __future__ import annotations

import asyncio
from datetime import timedelta

import nats
import redis.asyncio as redis
import structlog
from nats.errors import TimeoutError as NatsTimeoutError

from .config import Config
from .http_client import ParseError, PermanentFailureError
from .metrics import LISTINGS_SCRAPED, SCRAPE_DURATION, SCRAPE_ERRORS
from .models import ScraperCommand
from .quarantine import QuarantineStore
from .spiders import get_spider


LOGGER = structlog.get_logger(__name__)


async def run(config: Config) -> None:
    """Run the pull-based JetStream consumer loop."""

    nc = await nats.connect(config.nats_url)
    js = nc.jetstream()
    sub = await js.pull_subscribe(
        config.consumer_subject,
        durable=config.consumer_durable,
        stream=config.consumer_stream,
    )

    LOGGER.info(
        "consumer_started",
        stream=config.consumer_stream,
        durable=config.consumer_durable,
        subject=config.consumer_subject,
    )

    try:
        while True:
            try:
                messages = await sub.fetch(batch=1, timeout=1)
            except NatsTimeoutError:
                continue
            for message in messages:
                await process_message(message, js, config)
    except asyncio.CancelledError:
        LOGGER.info("consumer_cancelled")
        raise
    finally:
        await nc.close()


async def process_message(message, js, config: Config) -> None:
    """Process a single scrape command message."""

    try:
        command = ScraperCommand.model_validate_json(message.data)
    except Exception as exc:  # noqa: BLE001
        SCRAPE_ERRORS.labels(portal="unknown", country="unknown", error_type="parse_error").inc()
        LOGGER.error("invalid_scraper_command", error=str(exc))
        await _safe_terminal_ack(message)
        return

    spider_cls = get_spider(command.country, command.portal)
    if spider_cls is None:
        SCRAPE_ERRORS.labels(
            portal=command.portal,
            country=command.country,
            error_type="unknown_portal",
        ).inc()
        await message.nak()
        return

    spider = spider_cls(config)
    spider.search_url = command.search_url

    try:
        if command.mode == "detect_new":
            await _run_detect_new(spider, command, js, config)
        else:
            await _run_full_scrape(spider, command, js, config)
        await message.ack()
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
        await message.nak(delay=timedelta(seconds=config.transient_retry_delay_seconds))
    finally:
        await spider.close()


async def _run_full_scrape(spider, command: ScraperCommand, js, config: Config) -> None:
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
                        await _publish_listing(js, listing)
                        LISTINGS_SCRAPED.labels(
                            portal=spider.PORTAL,
                            country=spider.COUNTRY.lower(),
                        ).inc()
                    page += 1
    finally:
        await quarantine_redis.aclose()


async def _run_detect_new(spider, command: ScraperCommand, js, config: Config) -> None:
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

                await _publish_listing(js, listing)
                await spider._mark_seen(spider.redis, zone, {listing.external_id})
                LISTINGS_SCRAPED.labels(
                    portal=spider.PORTAL,
                    country=spider.COUNTRY.lower(),
                ).inc()
    finally:
        await quarantine_redis.aclose()


async def _publish_listing(js, listing) -> None:
    await js.publish(
        f"raw.listings.{listing.country_code.lower()}",
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


async def _safe_terminal_ack(message) -> None:
    if hasattr(message, "term"):
        await message.term()
        return
    await message.ack()
