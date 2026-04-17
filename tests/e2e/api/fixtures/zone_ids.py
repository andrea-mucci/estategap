from __future__ import annotations

import pytest

from tests.e2e.helpers.fixtures import SeededIDs


@pytest.fixture(scope="session")
def zone_ids_by_country(seeded_ids: SeededIDs) -> dict[str, list[str]]:
    return seeded_ids.zone_ids_by_country
