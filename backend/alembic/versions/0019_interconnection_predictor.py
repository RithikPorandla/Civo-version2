"""Add ferc_queue table for historical interconnection training data.

Revision ID: 0019
Revises: 0018
Create Date: 2026-05-06
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0019"
down_revision: Union[str, None] = "0018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()

    # ferc_queue — national FERC eQueue, filtered to ISO-NE.
    # Provides historical completed/withdrawn interconnection requests
    # going back to ~2000, giving far more training data than MA-only IRTT.
    if not bind.execute(sa.text(
        "SELECT 1 FROM information_schema.tables "
        "WHERE table_schema='public' AND table_name='ferc_queue'"
    )).fetchone():
        op.create_table(
            "ferc_queue",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("queue_id", sa.Text(), unique=True, nullable=False),
            sa.Column("project_name", sa.Text()),
            sa.Column("iso_rto", sa.Text()),        # 'ISO-NE', 'PJM', etc.
            sa.Column("state", sa.Text()),
            sa.Column("county", sa.Text()),
            sa.Column("project_type", sa.Text()),   # solar_ground_mount, bess_standalone, wind, other
            sa.Column("capacity_mw", sa.Float()),
            sa.Column("queue_date", sa.Date()),
            sa.Column("status", sa.Text()),         # active, completed, withdrawn, suspended
            sa.Column("in_service_date", sa.Date(), nullable=True),
            sa.Column("withdrawn_date", sa.Date(), nullable=True),
            sa.Column("study_phase", sa.Text(), nullable=True),
            sa.Column("source_year", sa.Integer(), nullable=True),
            sa.Column("ingested_at", sa.DateTime(timezone=True)),
        )
        op.execute(sa.text(
            "CREATE INDEX IF NOT EXISTS idx_ferc_queue_iso ON ferc_queue (iso_rto)"
        ))
        op.execute(sa.text(
            "CREATE INDEX IF NOT EXISTS idx_ferc_queue_state ON ferc_queue (state)"
        ))
        op.execute(sa.text(
            "CREATE INDEX IF NOT EXISTS idx_ferc_queue_type ON ferc_queue (project_type)"
        ))
        op.execute(sa.text(
            "CREATE INDEX IF NOT EXISTS idx_ferc_queue_status ON ferc_queue (status)"
        ))


def downgrade() -> None:
    op.drop_index("idx_ferc_queue_status")
    op.drop_index("idx_ferc_queue_type")
    op.drop_index("idx_ferc_queue_state")
    op.drop_index("idx_ferc_queue_iso")
    op.drop_table("ferc_queue")
