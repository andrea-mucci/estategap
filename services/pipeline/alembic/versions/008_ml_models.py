"""Create ML model registry table."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "b2c3d4e5f6a2"
down_revision = "a1b2c3d4e5f7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ml_model_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("country_code", sa.CHAR(length=2), nullable=False),
        sa.Column("algorithm", sa.String(length=30), nullable=False, server_default=sa.text("'lightgbm'")),
        sa.Column("version_tag", sa.String(length=40), nullable=False),
        sa.Column("artifact_path", sa.Text(), nullable=False),
        sa.Column("dataset_ref", sa.Text(), nullable=True),
        sa.Column("feature_names", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("metrics", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("status", sa.String(length=20), nullable=False, server_default=sa.text("'staging'")),
        sa.Column("trained_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("promoted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retired_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.ForeignKeyConstraint(["country_code"], ["countries.code"], name="fk_ml_model_versions_country_code_countries"),
        sa.PrimaryKeyConstraint("id", name="pk_ml_model_versions"),
        sa.UniqueConstraint("version_tag", name="uq_ml_model_versions_version_tag"),
    )
    op.create_index("ix_ml_model_versions_country_code_status", "ml_model_versions", ["country_code", "status"], unique=False)
    op.create_index(
        "uq_ml_model_versions_active_country",
        "ml_model_versions",
        ["country_code"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )


def downgrade() -> None:
    op.drop_index("uq_ml_model_versions_active_country", table_name="ml_model_versions")
    op.drop_index("ix_ml_model_versions_country_code_status", table_name="ml_model_versions")
    op.drop_table("ml_model_versions")
