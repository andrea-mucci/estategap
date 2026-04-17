from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import nats
import pytest

from estategap_common.models.listing import RawListing
from estategap_spiders.consumer import run
from estategap_spiders.models import ScraperCommand


testcontainers = pytest.importorskip("testcontainers.core.container")


@pytest.mark.asyncio
async def test_nats_consumer_round_trip(spider_config) -> None:
    container = (
        testcontainers.DockerContainer("nats:2.10-alpine")
        .with_exposed_ports(4222)
        .with_command("-js")
    )
    try:
        container.start()
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"Docker is not available for NATS integration test: {exc}")
    try:
        port = container.get_exposed_port(4222)
        nats_url = f"nats://{container.get_container_host_ip()}:{port}"
        config = spider_config.model_copy(update={"nats_url": nats_url})

        nc = await nats.connect(nats_url)
        js = nc.jetstream()
        await js.add_stream(name="SCRAPER_COMMANDS", subjects=["scraper.commands.>"])
        await js.add_stream(name="RAW_LISTINGS", subjects=["raw.listings.>"])
        subscriber = await nc.subscribe("raw.listings.es")

        consumer_task = asyncio.create_task(run(config))
        await asyncio.sleep(1)

        command = ScraperCommand(
            job_id="job-1",
            portal="fixture",
            country="ES",
            mode="full",
            zone_filter=["madrid-centro"],
            search_url="https://example.com/search",
            created_at=datetime.now(UTC),
        )
        await js.publish("scraper.commands.es.fixture", command.model_dump_json().encode())

        message = await subscriber.next_msg(timeout=5)
        listing = RawListing.model_validate_json(message.data)
        assert listing.portal == "fixture"
        assert listing.country_code == "ES"

        consumer_task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await consumer_task
        await nc.close()
    finally:
        container.stop()
