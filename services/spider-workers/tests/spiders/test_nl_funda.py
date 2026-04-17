from __future__ import annotations

import asyncio

import pytest

from estategap_spiders.spiders import nl_funda as nl_funda_module
from estategap_spiders.spiders.nl_funda import FundaSpider
from estategap_spiders.spiders.nl_funda_parser import extract_nuxt_data
from tests.spiders.conftest import read_fixture


def test_extract_nuxt_json() -> None:
    data = extract_nuxt_data(read_fixture("nl_funda_search.html"))

    assert len(data["listings"]) == 1
    assert data["listings"][0]["bag_id"] == "0363100012345678"


@pytest.mark.asyncio
async def test_rate_limiting_waits_for_remaining_interval(spider_config, monkeypatch) -> None:
    spider = FundaSpider(spider_config)
    spider._last_request_started = 10.0
    sleeps: list[float] = []
    points = iter([11.0, 12.0])

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)
    monkeypatch.setattr(nl_funda_module, "monotonic", lambda: next(points))

    await spider._enforce_rate_limit()

    assert sleeps == [1.0]

