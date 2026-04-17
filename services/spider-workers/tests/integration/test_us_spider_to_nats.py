from __future__ import annotations

import asyncio
from datetime import UTC, datetime
import json

import pytest

from estategap_common.models.listing import RawListing
from estategap_spiders.consumer import run
from estategap_spiders.models import ScraperCommand
from estategap_spiders.spiders.us_redfin import RedfinUSSpider


nats = pytest.importorskip("nats")
testcontainers = pytest.importorskip("testcontainers.core.container")


@pytest.mark.asyncio
async def test_redfin_spider_publishes_us_listing_to_nats(spider_config, monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_fetch_json(self, url: str):
        del self
        if "aboveTheFold" in url or "schoolsData" in url:
            pytest.fail("full scrape should only request the search endpoint")
        return {
            "payload": {
                "searchResults": [
                    {
                        "id": "RF123",
                        "url": "https://www.redfin.com/NY/New-York/10-Broadway-10004/home/12345",
                        "price": 880000,
                        "sqFt": 1200,
                        "beds": 3,
                        "baths": 2,
                        "propertyType": "Condo",
                        "lat": 40.706,
                        "lng": -74.011,
                        "streetLine": "10 Broadway",
                        "city": "New York",
                        "state": "NY",
                        "zip": "10004",
                    }
                ]
            }
        }

    monkeypatch.setattr(RedfinUSSpider, "_fetch_json", fake_fetch_json)

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
        subscriber = await nc.subscribe("raw.listings.us")

        consumer_task = asyncio.create_task(run(config))
        await asyncio.sleep(1)

        command = ScraperCommand(
            job_id="job-us-redfin-1",
            portal="redfin",
            country="US",
            mode="full",
            zone_filter=["10001"],
            search_url="https://www.redfin.com/stingray/api/gis?market=newyork",
            created_at=datetime.now(UTC),
        )
        await js.publish("scraper.commands.us.redfin", command.model_dump_json().encode())

        message = await subscriber.next_msg(timeout=5)
        listing = RawListing.model_validate_json(message.data)
        assert listing.portal == "redfin"
        assert listing.country_code == "US"
        assert listing.raw_json["price_usd_cents"] == 88_000_000
        assert listing.raw_json["area_m2"] == pytest.approx(111.48)

        consumer_task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await consumer_task
        await nc.close()
    finally:
        container.stop()
