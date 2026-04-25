"""town_jurisdiction_risk table.

Stores per-town, per-project-type permitting risk signals derived from
existing DB data (precedents, municipal_doer_adoption, municipalities.moratoriums).
Applied as a rank multiplier in discovery ORDER BY — kept separate from the
spatial score so jurisdiction data can refresh without invalidating cached scores.

Revision ID: 0010
Revises: 0009
Create Date: 2026-04-20
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "town_jurisdiction_risk",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("town_name", sa.Text, nullable=False),
        sa.Column("project_type", sa.Text, nullable=False),
        sa.Column("risk_multiplier", sa.Float, nullable=False, server_default="1.0"),
        sa.Column("moratorium_active", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("doer_status", sa.Text, nullable=True),
        sa.Column("concom_approval_rate", sa.Float, nullable=True),
        sa.Column("median_permit_days", sa.Integer, nullable=True),
        sa.Column("total_precedents", sa.Integer, nullable=False, server_default="0"),
        sa.Column(
            "computed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.UniqueConstraint("town_name", "project_type", name="uq_tjr_town_project"),
    )
    op.create_index(
        "ix_tjr_town_name", "town_jurisdiction_risk", ["town_name"]
    )
    op.create_index(
        "ix_tjr_project_type", "town_jurisdiction_risk", ["project_type"]
    )


def downgrade() -> None:
    op.drop_table("town_jurisdiction_risk")
