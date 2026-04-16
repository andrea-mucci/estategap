"""User, alert-rule, and alert-log schema tests."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Engine

from .conftest import collect_plan_values


def test_user_insert_and_retrieve(db_engine: Engine, user_factory) -> None:
    email = "user-alerts@example.com"
    user_id = user_factory(email=email, subscription_tier="starter", alert_limit=5)

    with db_engine.connect() as connection:
        row = connection.execute(
            text("SELECT id, email, subscription_tier, alert_limit FROM users WHERE email = :email"),
            {"email": email},
        ).mappings().one()

    assert row["id"] == user_id
    assert row["subscription_tier"] == "starter"
    assert row["alert_limit"] == 5


def test_soft_delete_index(db_engine: Engine, user_factory) -> None:
    email = "deleted-user@example.com"
    user_factory(email=email, deleted_at="2026-04-16T00:00:00+00:00")

    with db_engine.connect() as connection:
        row = connection.execute(
            text("SELECT id FROM users WHERE email = :email AND deleted_at IS NULL"),
            {"email": email},
        ).first()

    assert row is None


def test_alert_rule_fk(db_engine: Engine, user_factory, alert_rule_factory) -> None:
    user_id = user_factory()
    rule_id = alert_rule_factory(user_id=user_id, name="Barcelona deals")

    with db_engine.connect() as connection:
        count = connection.execute(
            text("SELECT COUNT(*) FROM alert_rules WHERE id = :rule_id AND user_id = :user_id"),
            {"rule_id": rule_id, "user_id": user_id},
        ).scalar_one()

    assert count == 1


def test_gin_filter_query(db_engine: Engine, explain_json, user_factory, alert_rule_factory) -> None:
    user_id = user_factory()
    alert_rule_factory(user_id=user_id, filters={"country": "ES", "max_price_eur": 300000})

    plan = explain_json(
        "SELECT * FROM alert_rules WHERE filters @> CAST(:needle AS jsonb)",
        {"needle": json.dumps({"country": "ES"})},
        disable_seqscan=True,
    )

    assert "alert_rules_filters_gin_idx" in collect_plan_values(plan, "Index Name")


def test_alert_log_delivery(db_engine: Engine, user_factory, alert_rule_factory, listing_factory) -> None:
    user_id = user_factory()
    rule_id = alert_rule_factory(user_id=user_id)
    listing_id = listing_factory()

    with db_engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO alert_log (rule_id, listing_id, country, channel, status, sent_at)
                VALUES (:rule_id, :listing_id, 'ES', 'email', 'sent', NOW())
                """
            ),
            {"rule_id": rule_id, "listing_id": listing_id},
        )

    with db_engine.connect() as connection:
        row = connection.execute(
            text(
                """
                SELECT channel, status
                FROM alert_log
                WHERE rule_id = :rule_id
                ORDER BY sent_at DESC
                LIMIT 1
                """
            ),
            {"rule_id": rule_id},
        ).mappings().one()

    assert row["channel"] == "email"
    assert row["status"] == "sent"
