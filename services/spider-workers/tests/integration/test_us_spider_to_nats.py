from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import pytest
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from estategap_common.testing.kafka import KafkaTestContainer

from estategap_common.models.listing import RawListing
from estategap_spiders.consumer import run
from estategap_spiders.models import ScraperCommand
from estategap_spiders.spiders.us_redfin import RedfinUSSpider

pytest.importorskip("testcontainers.kafka")


@pytest.mark.asyncio
async def test_redfin_spider_publishes_us_listing_to_kafka(
    spider_config,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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

    with KafkaTestContainer() as container:
        bootstrap = container.get_bootstrap_server()
        config = spider_config.model_copy(update={"kafka_brokers": bootstrap})

        subscriber = AIOKafkaConsumer(
            "estategap.raw-listings",
            bootstrap_servers=bootstrap,
            group_id="spider-redfin-test",
            enable_auto_commit=False,
            auto_offset_reset="earliest",
        )
        publisher = AIOKafkaProducer(bootstrap_servers=bootstrap)
        await subscriber.start()
        await publisher.start()

        consumer_task = asyncio.create_task(run(config))
        try:
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
            await publisher.send_and_wait(
                "estategap.scraper-commands",
                key=b"US.redfin",
                value=command.model_dump_json().encode(),
            )

            message = await _next_record(subscriber)
            listing = RawListing.model_validate_json(message.value)
            assert listing.portal == "redfin"
            assert listing.country_code == "US"
            assert listing.raw_json["price_usd_cents"] == 88_000_000
            assert listing.raw_json["area_m2"] == pytest.approx(111.48)
        finally:
            consumer_task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await consumer_task
            await subscriber.stop()
            await publisher.stop()


async def _next_record(consumer: AIOKafkaConsumer) -> object:
    deadline = asyncio.get_running_loop().time() + 10
    while asyncio.get_running_loop().time() < deadline:
        records = await consumer.getmany(timeout_ms=1000)
        for partition_records in records.values():
            if partition_records:
                return partition_records[0]
    raise AssertionError("timed out waiting for Kafka record")
