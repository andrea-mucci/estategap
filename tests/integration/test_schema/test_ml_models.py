"""ML model registry tests."""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError


def test_model_version_insert(db_engine: Engine, ml_model_factory) -> None:
    model_id = ml_model_factory(metrics={"mae": 15000, "rmse": 22000, "r2": 0.87})

    with db_engine.connect() as connection:
        row = connection.execute(
            text("SELECT metrics, status FROM ml_model_versions WHERE id = :model_id"),
            {"model_id": model_id},
        ).mappings().one()

    assert row["metrics"]["mae"] == 15000
    assert row["status"] == "staging"


def test_active_model_partial_unique(db_engine: Engine, ml_model_factory) -> None:
    ml_model_factory(country_code="ES", status="active", version_tag="es-active-one")
    with pytest.raises(IntegrityError):
        ml_model_factory(country_code="ES", status="active", version_tag="es-active-two")


def test_metrics_jsonb_access(db_engine: Engine, ml_model_factory) -> None:
    ml_model_factory(country_code="ES", version_tag="es-jsonb-metrics")

    with db_engine.connect() as connection:
        mae = connection.execute(
            text("SELECT metrics->>'mae' FROM ml_model_versions WHERE country_code = 'ES'"),
        ).scalar_one()

    assert mae == "15000"
