"""hosting_capacity table for HCA/HBA grid data.

Stores per-circuit/substation hosting capacity published by Eversource and
National Grid under their respective Grid Modernization filings. Used by
the grid_alignment scoring criterion to supplement ESMP proximity with
actual available capacity.

Revision ID: 0011
Revises: 0010
Create Date: 2026-04-21
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from geoalchemy2 import Geometry

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "hosting_capacity",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("utility", sa.Text, nullable=False),
        sa.Column("circuit_id", sa.Text, nullable=True),
        sa.Column("substation_name", sa.Text, nullable=True),
        sa.Column("voltage_kv", sa.Float, nullable=True),
        sa.Column("available_mw", sa.Float, nullable=False),
        sa.Column("technology", sa.Text, nullable=False, server_default="all"),
        sa.Column("data_year", sa.Integer, nullable=True),
        sa.Column("source_url", sa.Text, nullable=True),
        sa.Column("attrs", sa.dialects.postgresql.JSONB, nullable=True),
        sa.Column(
            "geom",
            Geometry("POINT", srid=26986),
            nullable=False,
        ),
        sa.Column(
            "ingested_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.CheckConstraint(
            "technology IN ('solar', 'bess', 'all')",
            name="ck_hca_technology",
        ),
    )
    op.create_index("ix_hca_utility", "hosting_capacity", ["utility"])
    op.create_index("ix_hca_technology", "hosting_capacity", ["technology"])
    op.create_index(
        "ix_hca_geom",
        "hosting_capacity",
        ["geom"],
        postgresql_using="gist",
    )


def downgrade() -> None:
    op.drop_table("hosting_capacity")
