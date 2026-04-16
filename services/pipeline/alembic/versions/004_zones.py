"""Create zones table."""

from __future__ import annotations

from alembic import op
from geoalchemy2 import Geometry
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "d4e5f6a1b2c3"
down_revision = "c3d4e5f6a1b2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "zones",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("name_local", sa.String(length=150), nullable=True),
        sa.Column("country_code", sa.CHAR(length=2), nullable=False),
        sa.Column("level", sa.SmallInteger(), nullable=False),
        sa.Column("parent_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("geometry", Geometry(geometry_type="MULTIPOLYGON", srid=4326), nullable=True),
        sa.Column("bbox", Geometry(geometry_type="POLYGON", srid=4326), nullable=True),
        sa.Column("population", sa.Integer(), nullable=True),
        sa.Column("area_km2", sa.Numeric(10, 2), nullable=True),
        sa.Column("slug", sa.String(length=200), nullable=True),
        sa.Column("osm_id", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.ForeignKeyConstraint(["country_code"], ["countries.code"], name="fk_zones_country_code_countries"),
        sa.ForeignKeyConstraint(["parent_id"], ["zones.id"], name="fk_zones_parent_id_zones"),
        sa.PrimaryKeyConstraint("id", name="pk_zones"),
        sa.UniqueConstraint("slug", name="uq_zones_slug"),
    )
    op.create_index("zones_geometry_gist_idx", "zones", ["geometry"], unique=False, postgresql_using="gist")
    op.create_index("zones_bbox_gist_idx", "zones", ["bbox"], unique=False, postgresql_using="gist")
    op.create_index("ix_zones_country_code_level", "zones", ["country_code", "level"], unique=False)
    op.create_index(
        "ix_zones_parent_id",
        "zones",
        ["parent_id"],
        unique=False,
        postgresql_where=sa.text("parent_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_zones_parent_id", table_name="zones")
    op.drop_index("ix_zones_country_code_level", table_name="zones")
    op.drop_index("zones_bbox_gist_idx", table_name="zones")
    op.drop_index("zones_geometry_gist_idx", table_name="zones")
    op.drop_table("zones")
