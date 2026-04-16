"""Seed the initial countries and portals."""

from __future__ import annotations

from uuid import UUID

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "d4e5f6a1b2c4"
down_revision = "c3d4e5f6a1b3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    countries = sa.table(
        "countries",
        sa.column("code", sa.CHAR(length=2)),
        sa.column("name", sa.String(length=100)),
        sa.column("currency", sa.CHAR(length=3)),
        sa.column("active", sa.Boolean()),
        sa.column("config", postgresql.JSONB(astext_type=sa.Text())),
    )
    op.bulk_insert(
        countries,
        [
            {"code": "ES", "name": "Spain", "currency": "EUR", "active": True, "config": {}},
            {"code": "IT", "name": "Italy", "currency": "EUR", "active": True, "config": {}},
            {"code": "PT", "name": "Portugal", "currency": "EUR", "active": True, "config": {}},
            {"code": "FR", "name": "France", "currency": "EUR", "active": True, "config": {}},
            {"code": "GB", "name": "United Kingdom", "currency": "GBP", "active": True, "config": {}},
        ],
    )

    portals = sa.table(
        "portals",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("name", sa.String(length=60)),
        sa.column("country_code", sa.CHAR(length=2)),
        sa.column("base_url", sa.Text()),
        sa.column("spider_class", sa.String(length=80)),
        sa.column("enabled", sa.Boolean()),
        sa.column("config", postgresql.JSONB(astext_type=sa.Text())),
    )
    op.bulk_insert(
        portals,
        [
            {
                "id": UUID("11111111-1111-1111-1111-111111111111"),
                "name": "Idealista ES",
                "country_code": "ES",
                "base_url": "https://www.idealista.com",
                "spider_class": "IdealistaSpider",
                "enabled": True,
                "config": {},
            },
            {
                "id": UUID("11111111-1111-1111-1111-111111111112"),
                "name": "Fotocasa ES",
                "country_code": "ES",
                "base_url": "https://www.fotocasa.es",
                "spider_class": "FotocasaSpider",
                "enabled": True,
                "config": {},
            },
            {
                "id": UUID("22222222-2222-2222-2222-222222222221"),
                "name": "Immobiliare.it IT",
                "country_code": "IT",
                "base_url": "https://www.immobiliare.it",
                "spider_class": "ImmobiliareItSpider",
                "enabled": True,
                "config": {},
            },
            {
                "id": UUID("22222222-2222-2222-2222-222222222222"),
                "name": "Casa.it IT",
                "country_code": "IT",
                "base_url": "https://www.casa.it",
                "spider_class": "CasaItSpider",
                "enabled": True,
                "config": {},
            },
            {
                "id": UUID("33333333-3333-3333-3333-333333333331"),
                "name": "Imovirtual PT",
                "country_code": "PT",
                "base_url": "https://www.imovirtual.com",
                "spider_class": "ImovirtualSpider",
                "enabled": True,
                "config": {},
            },
            {
                "id": UUID("33333333-3333-3333-3333-333333333332"),
                "name": "Idealista PT",
                "country_code": "PT",
                "base_url": "https://www.idealista.pt",
                "spider_class": "IdealistaPortugalSpider",
                "enabled": True,
                "config": {},
            },
            {
                "id": UUID("44444444-4444-4444-4444-444444444441"),
                "name": "SeLoger FR",
                "country_code": "FR",
                "base_url": "https://www.seloger.com",
                "spider_class": "SeLogerSpider",
                "enabled": True,
                "config": {},
            },
            {
                "id": UUID("44444444-4444-4444-4444-444444444442"),
                "name": "LeBonCoin FR",
                "country_code": "FR",
                "base_url": "https://www.leboncoin.fr",
                "spider_class": "LeBonCoinSpider",
                "enabled": True,
                "config": {},
            },
            {
                "id": UUID("55555555-5555-5555-5555-555555555551"),
                "name": "Rightmove GB",
                "country_code": "GB",
                "base_url": "https://www.rightmove.co.uk",
                "spider_class": "RightmoveSpider",
                "enabled": True,
                "config": {},
            },
            {
                "id": UUID("55555555-5555-5555-5555-555555555552"),
                "name": "Zoopla GB",
                "country_code": "GB",
                "base_url": "https://www.zoopla.co.uk",
                "spider_class": "ZooplaSpider",
                "enabled": True,
                "config": {},
            },
        ],
    )


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM portals
        WHERE id IN (
            '11111111-1111-1111-1111-111111111111',
            '11111111-1111-1111-1111-111111111112',
            '22222222-2222-2222-2222-222222222221',
            '22222222-2222-2222-2222-222222222222',
            '33333333-3333-3333-3333-333333333331',
            '33333333-3333-3333-3333-333333333332',
            '44444444-4444-4444-4444-444444444441',
            '44444444-4444-4444-4444-444444444442',
            '55555555-5555-5555-5555-555555555551',
            '55555555-5555-5555-5555-555555555552'
        )
        """
    )
    op.execute("DELETE FROM countries WHERE code IN ('ES', 'IT', 'PT', 'FR', 'GB')")
