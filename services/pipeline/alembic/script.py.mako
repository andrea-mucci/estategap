# -*- coding: utf-8 -*-
"""${message}."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

${imports if imports else ""}

# revision identifiers, used by Alembic.
revision = ${repr(up_revision)}
down_revision = ${repr(down_revision)}
branch_labels = ${repr(branch_labels)}
depends_on = ${repr(depends_on)}


def upgrade() -> None:  # type: ignore[no-untyped-def]
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:  # type: ignore[no-untyped-def]
    ${downgrades if downgrades else "pass"}
