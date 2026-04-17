from __future__ import annotations

import pytest


pytestmark = [pytest.mark.api]


ADMIN_ENDPOINTS = [
    ("GET", "/api/v1/admin/scraping/stats"),
    ("GET", "/api/v1/admin/ml/models"),
    ("POST", "/api/v1/admin/ml/retrain"),
    ("GET", "/api/v1/admin/users"),
    ("GET", "/api/v1/admin/countries"),
    ("GET", "/api/v1/admin/system/health"),
]


@pytest.mark.asyncio
async def test_admin_endpoints_require_admin_role(authed_client) -> None:
    client = authed_client("pro")
    for method, path in ADMIN_ENDPOINTS:
        response = await client.request(method, path, json={"country": "ES"} if method == "POST" else None)
        assert response.status_code == 403, (path, response.text)


@pytest.mark.asyncio
async def test_admin_endpoints_work_for_admin(authed_client) -> None:
    admin = authed_client("admin")

    scraping = await admin.get("/api/v1/admin/scraping/stats")
    assert scraping.status_code == 200, scraping.text
    assert "portals" in scraping.json()

    ml_models = await admin.get("/api/v1/admin/ml/models")
    assert ml_models.status_code == 200, ml_models.text
    assert "models" in ml_models.json()

    retrain = await admin.post("/api/v1/admin/ml/retrain", json={"country": "ES"})
    if retrain.status_code == 503:
        pytest.skip("ML retraining backend is unavailable in this local environment")
    assert retrain.status_code == 200, retrain.text
    assert retrain.json()["status"] == "queued"

    users = await admin.get("/api/v1/admin/users", params={"page": 1, "limit": 10})
    assert users.status_code == 200, users.text
    assert "users" in users.json()

    countries = await admin.get("/api/v1/admin/countries")
    assert countries.status_code == 200, countries.text
    country = countries.json()["countries"][0]

    updated = await admin.put(
        f"/api/v1/admin/countries/{country['code']}",
        json={"enabled": country["enabled"], "portals": country["portals"]},
    )
    assert updated.status_code == 200, updated.text

    system = await admin.get("/api/v1/admin/system/health")
    assert system.status_code == 200, system.text
    assert "database" in system.json()
