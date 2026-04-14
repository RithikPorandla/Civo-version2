"""Add land_use table for MassGIS 2016 Land Cover/Land Use.

Revision ID: 0003_land_use
Revises: 0002_esmp_fields
Create Date: 2026-04-14
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from geoalchemy2 import Geometry
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0003_land_use"
down_revision: Union[str, None] = "0002_esmp_fields"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "land_use",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("town_id", sa.Integer, index=True),
        sa.Column("covercode", sa.Integer, index=True),
        sa.Column("covername", sa.String),
        sa.Column("usegencode", sa.Integer, index=True),
        sa.Column("usegenname", sa.String),
        sa.Column("use_code", sa.String),
        sa.Column("poly_type", sa.String),
        sa.Column("fy", sa.Integer),
        sa.Column("shape_area", sa.Float),
        sa.Column("attrs", JSONB),
        sa.Column(
            "geom",
            Geometry(geometry_type="MULTIPOLYGON", srid=26986, spatial_index=True),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("land_use")
