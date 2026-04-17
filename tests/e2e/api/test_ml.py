from __future__ import annotations

import pytest

from tests.e2e.helpers.fixtures import SeededIDs, require_items


pytestmark = [pytest.mark.api]


@pytest.mark.asyncio
async def test_ml_estimate_with_valid_listing_and_missing_param(authed_client, seeded_ids: SeededIDs) -> None:
    client = authed_client("global")
    listing_id = require_items(seeded_ids.listing_ids_by_country["ES"], "ES listing ids")[0]

    missing = await client.get("/api/v1/model/estimate")
    assert missing.status_code == 400, missing.text
    assert missing.json()["code"] == "INVALID_LISTING_ID"

    estimate = await client.get("/api/v1/model/estimate", params={"listing_id": listing_id})
    if estimate.status_code == 503:
        pytest.skip("ML scorer is not available in this local environment")
    assert estimate.status_code == 200, estimate.text
    payload = estimate.json()
    assert payload["listing_id"] == listing_id
    assert "shap_values" in payload
