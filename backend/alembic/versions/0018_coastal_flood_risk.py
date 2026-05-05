"""Add coastal_flood_risk table for MC-FRM 2030/2050/2070 inundation polygons.

Revision ID: 0018
Revises: 0017
Create Date: 2026-05-05
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from geoalchemy2 import Geometry
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0018"
down_revision: Union[str, None] = "0017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if not bind.execute(
        sa.text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema='public' AND table_name='coastal_flood_risk'"
        )
    ).fetchone():
        op.create_table(
            "coastal_flood_risk",
            sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
            sa.Column("scenario", sa.String(4), nullable=False),   # '2030', '2050', '2070'
            sa.Column("aep", sa.String(8), nullable=False),        # '1pct', '0.1pct'
            sa.Column("gridcode", sa.Integer, nullable=True),
            sa.Column("attrs", JSONB, nullable=True),
            sa.Column(
                "geom",
                Geometry(geometry_type="MULTIPOLYGON", srid=26986, spatial_index=True),
                nullable=False,
            ),
        )
        op.create_index(
            "ix_coastal_flood_risk_scenario_aep",
            "coastal_flood_risk",
            ["scenario", "aep"],
        )


def downgrade() -> None:
    op.drop_index("ix_coastal_flood_risk_scenario_aep", "coastal_flood_risk")
    op.drop_table("coastal_flood_risk")
