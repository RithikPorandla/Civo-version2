"""discovery_queries and discovery_followups tables.

Revision ID: 0009
Revises: 0008
Create Date: 2026-04-20
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0009"
down_revision = "0008_parcel_characterizations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    if not bind.execute(sa.text(
        "SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='discovery_queries'"
    )).fetchone():
        op.create_table(
            "discovery_queries",
            sa.Column("id", sa.Text, primary_key=True),
            sa.Column("state", sa.Text, nullable=False, server_default="MA"),
            sa.Column("query_text", sa.Text, nullable=False),
            sa.Column("intent_type", sa.Text, nullable=False),
            sa.Column("interpreted_filters", sa.dialects.postgresql.JSONB, nullable=False),
            sa.Column("result_count", sa.Integer, nullable=False),
            sa.Column("narrative", sa.Text, nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("NOW()"),
            ),
            sa.Column("user_session_id", sa.Text, nullable=True),
        )
        op.execute(sa.text(
            "CREATE INDEX IF NOT EXISTS ix_discovery_queries_created_at ON discovery_queries (created_at)"
        ))

    if not bind.execute(sa.text(
        "SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='discovery_followups'"
    )).fetchone():
        op.create_table(
            "discovery_followups",
            sa.Column("id", sa.Text, primary_key=True),
            sa.Column("parent_query_id", sa.Text, sa.ForeignKey("discovery_queries.id"), nullable=False),
            sa.Column("followup_text", sa.Text, nullable=False),
            sa.Column("interpreted_filters", sa.dialects.postgresql.JSONB, nullable=False),
            sa.Column("result_count", sa.Integer, nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("NOW()"),
            ),
        )
        op.execute(sa.text(
            "CREATE INDEX IF NOT EXISTS ix_discovery_followups_parent ON discovery_followups (parent_query_id)"
        ))


def downgrade() -> None:
    op.drop_table("discovery_followups")
    op.drop_table("discovery_queries")
