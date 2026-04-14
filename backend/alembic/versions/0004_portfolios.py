"""Add portfolios table.

Revision ID: 0004_portfolios
Revises: 0003_land_use
Create Date: 2026-04-14
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0004_portfolios"
down_revision: Union[str, None] = "0003_land_use"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "portfolios",
        sa.Column("id", sa.Text, primary_key=True),
        sa.Column(
            "state", sa.Text, nullable=False, server_default=sa.text("'MA'")
        ),
        sa.Column("name", sa.Text),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("items", JSONB, nullable=False),
        sa.Column("project_type", sa.Text),
        sa.Column("config_version", sa.Text, nullable=False),
        sa.Column("scored_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "portfolios_created_at_idx", "portfolios", [sa.text("created_at DESC")]
    )


def downgrade() -> None:
    op.drop_index("portfolios_created_at_idx", table_name="portfolios")
    op.drop_table("portfolios")
