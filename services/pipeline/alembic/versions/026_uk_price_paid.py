"""Create the UK Land Registry Price Paid reference table."""

from __future__ import annotations

from alembic import op

revision = "c7d8e9f0a1b2"
down_revision = "b6c7d8e9f0a1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS uk_price_paid (
            id BIGSERIAL PRIMARY KEY,
            transaction_uid UUID NOT NULL UNIQUE,
            price_gbp INTEGER NOT NULL,
            date_transfer DATE NOT NULL,
            postcode VARCHAR(8),
            property_type CHAR(1),
            old_new CHAR(1),
            tenure CHAR(1),
            paon TEXT,
            saon TEXT,
            street TEXT,
            locality TEXT,
            town_city TEXT,
            district TEXT,
            county TEXT,
            address_normalized TEXT,
            loaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS uk_price_paid_postcode_idx ON uk_price_paid (postcode)")
    op.execute(
        "CREATE INDEX IF NOT EXISTS uk_price_paid_transaction_uid_idx ON uk_price_paid (transaction_uid)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uk_price_paid_transaction_uid_idx")
    op.execute("DROP INDEX IF EXISTS uk_price_paid_postcode_idx")
    op.drop_table("uk_price_paid")
