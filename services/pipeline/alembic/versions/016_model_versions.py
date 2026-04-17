"""Normalize ML model registry into the model_versions table."""

from __future__ import annotations

from alembic import op

revision = "d1e2f3a4b5c6"
down_revision = "c0d1e2f3a4b5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM information_schema.tables
                WHERE table_name = 'ml_model_versions'
            ) AND NOT EXISTS (
                SELECT 1
                FROM information_schema.tables
                WHERE table_name = 'model_versions'
            ) THEN
                ALTER TABLE ml_model_versions RENAME TO model_versions;
            END IF;
        END
        $$;
        """
    )
    op.execute("ALTER INDEX IF EXISTS ix_ml_model_versions_country_code_status RENAME TO ix_model_versions_country_code_status")
    op.execute("ALTER TABLE model_versions DROP CONSTRAINT IF EXISTS uq_ml_model_versions_version_tag")
    op.execute("DROP INDEX IF EXISTS uq_ml_model_versions_active_country")
    op.execute("DROP INDEX IF EXISTS uq_model_versions_active_country")
    op.execute("DROP INDEX IF EXISTS ix_model_versions_country_code_status")
    op.execute("ALTER TABLE model_versions ALTER COLUMN algorithm TYPE VARCHAR(50)")
    op.execute("ALTER TABLE model_versions ALTER COLUMN version_tag TYPE VARCHAR(100)")
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_model_versions_country_code_status
        ON model_versions (country_code, status)
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_model_versions_country_version_tag
        ON model_versions (country_code, version_tag)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_model_versions_country_version_tag")
    op.execute("DROP INDEX IF EXISTS ix_model_versions_country_code_status")
    op.execute("ALTER TABLE model_versions ALTER COLUMN version_tag TYPE VARCHAR(40)")
    op.execute("ALTER TABLE model_versions ALTER COLUMN algorithm TYPE VARCHAR(30)")
    op.execute(
        """
        ALTER TABLE model_versions
        ADD CONSTRAINT uq_ml_model_versions_version_tag UNIQUE (version_tag)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_ml_model_versions_country_code_status
        ON model_versions (country_code, status)
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_ml_model_versions_active_country
        ON model_versions (country_code)
        WHERE status = 'active'
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM information_schema.tables
                WHERE table_name = 'model_versions'
            ) AND NOT EXISTS (
                SELECT 1
                FROM information_schema.tables
                WHERE table_name = 'ml_model_versions'
            ) THEN
                ALTER TABLE model_versions RENAME TO ml_model_versions;
            END IF;
        END
        $$;
        """
    )
