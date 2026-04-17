"""Create the France DVF transaction reference table."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "b6c7d8e9f0a1"
down_revision = "a5b6c7d8e9f0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS dvf_transactions (
            id BIGSERIAL PRIMARY KEY,
            date_mutation DATE NOT NULL,
            valeur_fonciere NUMERIC(14, 2) NOT NULL,
            type_local VARCHAR(50),
            surface_reelle_bati NUMERIC(10, 2),
            adresse_numero VARCHAR(10),
            adresse_nom_voie TEXT,
            code_postal VARCHAR(10),
            commune VARCHAR(150),
            geom geometry(POINT, 4326),
            loaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT uq_dvf_transaction UNIQUE (date_mutation, adresse_numero, adresse_nom_voie, valeur_fonciere)
        )
        """
    )
    op.create_index(
        "dvf_transactions_geom_idx",
        "dvf_transactions",
        ["geom"],
        unique=False,
        postgresql_using="gist",
    )
    op.create_index(
        "dvf_transactions_postal_type_idx",
        "dvf_transactions",
        ["code_postal", "type_local"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("dvf_transactions_postal_type_idx", table_name="dvf_transactions")
    op.drop_index("dvf_transactions_geom_idx", table_name="dvf_transactions", postgresql_using="gist")
    op.drop_table("dvf_transactions")
