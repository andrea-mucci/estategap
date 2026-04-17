"""Create visual_references for the AI chat service."""

from __future__ import annotations

from alembic import op

revision = "020_ai_chat_visual_references"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS visual_references (
            id UUID PRIMARY KEY,
            image_url TEXT NOT NULL,
            tags TEXT[] NOT NULL DEFAULT '{}',
            description TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_visual_references_tags
        ON visual_references USING GIN (tags)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_visual_references_tags")
    op.execute("DROP TABLE IF EXISTS visual_references")
