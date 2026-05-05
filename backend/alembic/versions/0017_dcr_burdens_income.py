"""Add dcr_priority_forests table and median_hh_income to massenviroscreen.

Revision ID: 0017
Revises: 0016
Create Date: 2026-05-05
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from geoalchemy2 import Geometry
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0017"
down_revision: Union[str, None] = "0016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()

    # Add median_hh_income to massenviroscreen (idempotent)
    existing_cols = {
        r[0]
        for r in bind.execute(
            sa.text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema='public' AND table_name='massenviroscreen'"
            )
        )
    }
    if "median_hh_income" not in existing_cols:
        op.add_column(
            "massenviroscreen",
            sa.Column("median_hh_income", sa.Numeric(12, 2)),
        )

    # Create dcr_priority_forests (idempotent)
    if not bind.execute(
        sa.text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema='public' AND table_name='dcr_priority_forests'"
        )
    ).fetchone():
        op.create_table(
            "dcr_priority_forests",
            sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
            sa.Column("forest_id", sa.String, index=True),
            sa.Column("forest_name", sa.String),
            sa.Column("carbon_tier", sa.String),
            sa.Column("attrs", JSONB),
            sa.Column(
                "geom",
                Geometry(geometry_type="MULTIPOLYGON", srid=26986, spatial_index=True),
                nullable=False,
            ),
        )


def downgrade() -> None:
    op.drop_table("dcr_priority_forests")
    op.drop_column("massenviroscreen", "median_hh_income")
