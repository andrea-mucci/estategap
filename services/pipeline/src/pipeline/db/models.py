"""SQLAlchemy metadata used by Alembic autogeneration."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

import sqlalchemy as sa
from geoalchemy2 import Geometry
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from .types import GeometryMultiPolygon, JSONB

JSONDict = dict[str, Any]
StringList = list[str]


class Base(DeclarativeBase):
    """Declarative base for pipeline schema metadata."""


class Country(Base):
    __tablename__ = "countries"

    code: Mapped[str] = mapped_column(sa.CHAR(2), primary_key=True)
    name: Mapped[str] = mapped_column(sa.String(100))
    currency: Mapped[str] = mapped_column(sa.CHAR(3))
    active: Mapped[bool] = mapped_column(sa.Boolean, server_default=sa.true(), nullable=False)
    config: Mapped[JSONDict] = mapped_column(
        JSONB,
        nullable=False,
        server_default=sa.text("'{}'::jsonb"),
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("NOW()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("NOW()"),
    )


class Portal(Base):
    __tablename__ = "portals"
    __table_args__ = (
        sa.UniqueConstraint("name", "country_code", name="uq_portals_name_country"),
        sa.Index("ix_portals_country_code_enabled", "country_code", "enabled"),
    )

    id: Mapped[UUID] = mapped_column(
        postgresql.UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    name: Mapped[str] = mapped_column(sa.String(60))
    country_code: Mapped[str] = mapped_column(
        sa.CHAR(2),
        sa.ForeignKey("countries.code"),
        nullable=False,
    )
    base_url: Mapped[str] = mapped_column(sa.Text)
    spider_class: Mapped[str] = mapped_column(sa.String(80))
    enabled: Mapped[bool] = mapped_column(sa.Boolean, server_default=sa.true(), nullable=False)
    config: Mapped[JSONDict] = mapped_column(
        JSONB,
        nullable=False,
        server_default=sa.text("'{}'::jsonb"),
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("NOW()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("NOW()"),
    )


class ExchangeRate(Base):
    __tablename__ = "exchange_rates"

    currency: Mapped[str] = mapped_column(sa.CHAR(3), primary_key=True)
    date: Mapped[date] = mapped_column(sa.Date, primary_key=True)
    rate_to_eur: Mapped[Decimal] = mapped_column(sa.Numeric(12, 6))
    fetched_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("NOW()"),
    )


class PriceHistory(Base):
    __tablename__ = "price_history"
    __table_args__ = (
        sa.Index("price_history_listing_id_recorded_at_idx", "listing_id", sa.text("recorded_at DESC")),
        sa.Index("ix_price_history_country_recorded_at", "country", sa.text("recorded_at DESC")),
    )

    id: Mapped[int] = mapped_column(sa.BigInteger, sa.Identity(), primary_key=True)
    listing_id: Mapped[UUID] = mapped_column(postgresql.UUID(as_uuid=True), nullable=False)
    country: Mapped[str] = mapped_column(sa.CHAR(2), nullable=False)
    old_price: Mapped[Decimal | None] = mapped_column(sa.Numeric(14, 2))
    new_price: Mapped[Decimal] = mapped_column(sa.Numeric(14, 2), nullable=False)
    currency: Mapped[str] = mapped_column(sa.CHAR(3), nullable=False)
    old_price_eur: Mapped[Decimal | None] = mapped_column(sa.Numeric(14, 2))
    new_price_eur: Mapped[Decimal | None] = mapped_column(sa.Numeric(14, 2))
    change_type: Mapped[str] = mapped_column(
        sa.String(20),
        nullable=False,
        server_default=sa.text("'price_change'"),
    )
    old_status: Mapped[str | None] = mapped_column(sa.String(20))
    new_status: Mapped[str | None] = mapped_column(sa.String(20))
    recorded_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("NOW()"),
    )
    source: Mapped[str | None] = mapped_column(sa.String(30))


class Zone(Base):
    __tablename__ = "zones"
    __table_args__ = (
        sa.Index("zones_geometry_gist_idx", "geometry", postgresql_using="gist"),
        sa.Index("zones_bbox_gist_idx", "bbox", postgresql_using="gist"),
        sa.Index("ix_zones_country_code_level", "country_code", "level"),
        sa.Index(
            "ix_zones_parent_id",
            "parent_id",
            postgresql_where=sa.text("parent_id IS NOT NULL"),
        ),
        sa.Index("ix_zones_slug", "slug"),
    )

    id: Mapped[UUID] = mapped_column(
        postgresql.UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    name: Mapped[str] = mapped_column(sa.String(150), nullable=False)
    name_local: Mapped[str | None] = mapped_column(sa.String(150))
    country_code: Mapped[str] = mapped_column(
        sa.CHAR(2),
        sa.ForeignKey("countries.code"),
        nullable=False,
    )
    level: Mapped[int] = mapped_column(sa.SmallInteger, nullable=False)
    parent_id: Mapped[UUID | None] = mapped_column(
        postgresql.UUID(as_uuid=True),
        sa.ForeignKey("zones.id"),
    )
    user_id: Mapped[UUID | None] = mapped_column(
        postgresql.UUID(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="CASCADE"),
    )
    geometry: Mapped[Any | None] = mapped_column(GeometryMultiPolygon)
    bbox: Mapped[Any | None] = mapped_column(Geometry(geometry_type="POLYGON", srid=4326))
    population: Mapped[int | None] = mapped_column(sa.Integer)
    area_km2: Mapped[Decimal | None] = mapped_column(sa.Numeric(10, 2))
    slug: Mapped[str | None] = mapped_column(sa.String(200), unique=True)
    osm_id: Mapped[int | None] = mapped_column(sa.BigInteger)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("NOW()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("NOW()"),
    )


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        sa.Index(
            "ix_users_email_active",
            "email",
            postgresql_where=sa.text("deleted_at IS NULL"),
        ),
        sa.Index(
            "ix_users_stripe_customer_id",
            "stripe_customer_id",
            postgresql_where=sa.text("stripe_customer_id IS NOT NULL"),
        ),
        sa.Index(
            "ix_users_oauth_provider_subject",
            "oauth_provider",
            "oauth_subject",
            postgresql_where=sa.text("oauth_provider IS NOT NULL"),
        ),
    )

    id: Mapped[UUID] = mapped_column(
        postgresql.UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    email: Mapped[str] = mapped_column(sa.String(255), nullable=False, unique=True)
    password_hash: Mapped[str | None] = mapped_column(sa.String(255))
    oauth_provider: Mapped[str | None] = mapped_column(sa.String(20))
    oauth_subject: Mapped[str | None] = mapped_column(sa.String(100))
    display_name: Mapped[str | None] = mapped_column(sa.String(100))
    avatar_url: Mapped[str | None] = mapped_column(sa.Text)
    subscription_tier: Mapped[str] = mapped_column(
        sa.String(20),
        nullable=False,
        server_default=sa.text("'free'"),
    )
    preferred_currency: Mapped[str] = mapped_column(
        sa.String(3),
        nullable=False,
        server_default=sa.text("'EUR'"),
    )
    allowed_countries: Mapped[StringList] = mapped_column(
        postgresql.ARRAY(sa.CHAR(2)),
        nullable=False,
        server_default=sa.text("'{}'"),
    )
    stripe_customer_id: Mapped[str | None] = mapped_column(sa.String(30), unique=True)
    stripe_sub_id: Mapped[str | None] = mapped_column(sa.String(30), unique=True)
    subscription_ends_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    alert_limit: Mapped[int] = mapped_column(
        sa.SmallInteger,
        nullable=False,
        server_default=sa.text("3"),
    )
    email_verified: Mapped[bool] = mapped_column(
        sa.Boolean,
        nullable=False,
        server_default=sa.false(),
    )
    email_verified_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    last_login_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("NOW()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("NOW()"),
    )


class AlertRule(Base):
    __tablename__ = "alert_rules"
    __table_args__ = (
        sa.Index("idx_alert_rules_user_id", "user_id"),
        sa.Index("idx_alert_rules_user_active", "user_id", postgresql_where=sa.text("is_active = TRUE")),
    )

    id: Mapped[UUID] = mapped_column(
        postgresql.UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    user_id: Mapped[UUID] = mapped_column(
        postgresql.UUID(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    zone_ids: Mapped[StringList] = mapped_column(
        postgresql.ARRAY(postgresql.UUID(as_uuid=True)),
        nullable=False,
        server_default=sa.text("'{}'::uuid[]"),
    )
    category: Mapped[str] = mapped_column(sa.String(50), nullable=False)
    filter: Mapped[JSONDict] = mapped_column(
        JSONB,
        nullable=False,
        server_default=sa.text("'{}'::jsonb"),
    )
    channels: Mapped[list[JSONDict]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=sa.text("'[]'::jsonb"),
    )
    frequency: Mapped[str] = mapped_column(
        sa.String(10),
        nullable=False,
        server_default=sa.text("'instant'"),
    )
    is_active: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, server_default=sa.true())
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("NOW()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("NOW()"),
    )


class PortfolioProperty(Base):
    __tablename__ = "portfolio_properties"
    __table_args__ = (
        sa.Index("idx_portfolio_properties_user_id", "user_id"),
        sa.Index("idx_portfolio_properties_country", "country"),
    )

    id: Mapped[UUID] = mapped_column(
        postgresql.UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    user_id: Mapped[UUID] = mapped_column(
        postgresql.UUID(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    address: Mapped[str] = mapped_column(sa.Text, nullable=False)
    lat: Mapped[float | None] = mapped_column(sa.Float)
    lng: Mapped[float | None] = mapped_column(sa.Float)
    zone_id: Mapped[UUID | None] = mapped_column(
        postgresql.UUID(as_uuid=True),
        sa.ForeignKey("zones.id"),
    )
    country: Mapped[str] = mapped_column(sa.String(2), nullable=False)
    purchase_price: Mapped[Decimal] = mapped_column(sa.Numeric(18, 4), nullable=False)
    purchase_currency: Mapped[str] = mapped_column(sa.String(3), nullable=False)
    purchase_price_eur: Mapped[Decimal] = mapped_column(sa.Numeric(18, 4), nullable=False)
    purchase_date: Mapped[date] = mapped_column(sa.Date, nullable=False)
    monthly_rental_income: Mapped[Decimal] = mapped_column(
        sa.Numeric(18, 4),
        nullable=False,
        server_default=sa.text("0"),
    )
    monthly_rental_income_eur: Mapped[Decimal] = mapped_column(
        sa.Numeric(18, 4),
        nullable=False,
        server_default=sa.text("0"),
    )
    area_m2: Mapped[Decimal | None] = mapped_column(sa.Numeric(10, 2))
    property_type: Mapped[str] = mapped_column(
        sa.String(20),
        nullable=False,
        server_default=sa.text("'residential'"),
    )
    notes: Mapped[str | None] = mapped_column(sa.Text)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("NOW()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("NOW()"),
    )


class AlertHistory(Base):
    __tablename__ = "alert_history"
    __table_args__ = (
        sa.Index("idx_alert_history_rule_id", "rule_id", sa.text("triggered_at DESC")),
        sa.Index("idx_alert_history_user", "rule_id"),
    )

    id: Mapped[UUID] = mapped_column(
        postgresql.UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    rule_id: Mapped[UUID] = mapped_column(
        postgresql.UUID(as_uuid=True),
        sa.ForeignKey("alert_rules.id", ondelete="CASCADE"),
        nullable=False,
    )
    listing_id: Mapped[UUID] = mapped_column(postgresql.UUID(as_uuid=True), nullable=False)
    channel: Mapped[str] = mapped_column(sa.String(20), nullable=False)
    delivery_status: Mapped[str] = mapped_column(
        sa.String(20),
        nullable=False,
        server_default=sa.text("'pending'"),
    )
    error_detail: Mapped[str | None] = mapped_column(sa.Text)
    delivered_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    triggered_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("NOW()"),
    )


class AiConversation(Base):
    __tablename__ = "ai_conversations"
    __table_args__ = (
        sa.Index("ai_conversations_user_id_status_idx", "user_id", "status"),
        sa.Index(
            "ix_ai_conversations_status_updated_at",
            "status",
            "updated_at",
            postgresql_where=sa.text("status = 'active'"),
        ),
    )

    id: Mapped[UUID] = mapped_column(
        postgresql.UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    user_id: Mapped[UUID | None] = mapped_column(
        postgresql.UUID(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="SET NULL"),
    )
    language: Mapped[str] = mapped_column(
        sa.CHAR(2),
        nullable=False,
        server_default=sa.text("'en'"),
    )
    criteria_state: Mapped[JSONDict] = mapped_column(
        JSONB,
        nullable=False,
        server_default=sa.text("'{}'::jsonb"),
    )
    alert_rule_id: Mapped[UUID | None] = mapped_column(
        postgresql.UUID(as_uuid=True),
        sa.ForeignKey("alert_rules.id", ondelete="SET NULL"),
    )
    turn_count: Mapped[int] = mapped_column(
        sa.SmallInteger,
        nullable=False,
        server_default=sa.text("0"),
    )
    status: Mapped[str] = mapped_column(
        sa.String(20),
        nullable=False,
        server_default=sa.text("'active'"),
    )
    model_used: Mapped[str | None] = mapped_column(sa.String(60))
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("NOW()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("NOW()"),
    )


class AiMessage(Base):
    __tablename__ = "ai_messages"
    __table_args__ = (sa.Index("ai_messages_conversation_id_id_idx", "conversation_id", "id"),)

    id: Mapped[int] = mapped_column(sa.BigInteger, sa.Identity(), primary_key=True)
    conversation_id: Mapped[UUID] = mapped_column(
        postgresql.UUID(as_uuid=True),
        sa.ForeignKey("ai_conversations.id", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(sa.String(10), nullable=False)
    content: Mapped[str] = mapped_column(sa.Text, nullable=False)
    criteria_snapshot: Mapped[JSONDict] = mapped_column(
        JSONB,
        nullable=False,
        server_default=sa.text("'{}'::jsonb"),
    )
    visual_refs: Mapped[StringList] = mapped_column(
        JSONB,
        nullable=False,
        server_default=sa.text("'[]'::jsonb"),
    )
    tokens_used: Mapped[int | None] = mapped_column(sa.Integer)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("NOW()"),
    )


class MlModelVersion(Base):
    __tablename__ = "model_versions"
    __table_args__ = (
        sa.Index("ix_model_versions_country_code_status", "country_code", "status"),
        sa.UniqueConstraint("country_code", "version_tag", name="uq_model_versions_country_version_tag"),
    )

    id: Mapped[UUID] = mapped_column(
        postgresql.UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    country_code: Mapped[str] = mapped_column(
        sa.CHAR(2),
        sa.ForeignKey("countries.code"),
        nullable=False,
    )
    algorithm: Mapped[str] = mapped_column(
        sa.String(50),
        nullable=False,
        server_default=sa.text("'lightgbm'"),
    )
    version_tag: Mapped[str] = mapped_column(sa.String(100), nullable=False)
    artifact_path: Mapped[str] = mapped_column(sa.Text, nullable=False)
    dataset_ref: Mapped[str | None] = mapped_column(sa.Text)
    feature_names: Mapped[StringList] = mapped_column(
        JSONB,
        nullable=False,
        server_default=sa.text("'[]'::jsonb"),
    )
    metrics: Mapped[JSONDict] = mapped_column(
        JSONB,
        nullable=False,
        server_default=sa.text("'{}'::jsonb"),
    )
    status: Mapped[str] = mapped_column(
        sa.String(20),
        nullable=False,
        server_default=sa.text("'staging'"),
    )
    trained_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("NOW()"),
    )
    promoted_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    retired_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("NOW()"),
    )
