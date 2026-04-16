"""Create AI conversation and message tables."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "a1b2c3d4e5f7"
down_revision = "f6a1b2c3d4e5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_conversations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("language", sa.CHAR(length=2), nullable=False, server_default=sa.text("'en'")),
        sa.Column("criteria_state", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("alert_rule_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("turn_count", sa.SmallInteger(), nullable=False, server_default=sa.text("0")),
        sa.Column("status", sa.String(length=20), nullable=False, server_default=sa.text("'active'")),
        sa.Column("model_used", sa.String(length=60), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.ForeignKeyConstraint(["alert_rule_id"], ["alert_rules.id"], name="fk_ai_conversations_alert_rule_id_alert_rules", ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_ai_conversations_user_id_users", ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_ai_conversations"),
    )
    op.create_index("ai_conversations_user_id_status_idx", "ai_conversations", ["user_id", "status"], unique=False)

    op.create_table(
        "ai_messages",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(length=10), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("criteria_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("visual_refs", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("tokens_used", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.CheckConstraint("role IN ('user', 'assistant', 'system')", name="ck_ai_messages_role"),
        sa.ForeignKeyConstraint(["conversation_id"], ["ai_conversations.id"], name="fk_ai_messages_conversation_id_ai_conversations", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_ai_messages"),
    )
    op.create_index("ai_messages_conversation_id_id_idx", "ai_messages", ["conversation_id", "id"], unique=False)


def downgrade() -> None:
    op.drop_index("ai_messages_conversation_id_id_idx", table_name="ai_messages")
    op.drop_table("ai_messages")
    op.drop_index("ai_conversations_user_id_status_idx", table_name="ai_conversations")
    op.drop_table("ai_conversations")
