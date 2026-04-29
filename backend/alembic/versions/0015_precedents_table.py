"""Create precedents table (was missing from initial schema migration).

Revision ID: 0015_precedents_table
Revises: 0014
Create Date: 2026-04-29
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from geoalchemy2 import Geometry
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import ARRAY

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None

SRID = 26986


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "precedents",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("town_id", sa.Integer, sa.ForeignKey("municipalities.town_id"), index=True, nullable=True),
        sa.Column("docket", sa.String, index=True, nullable=True),
        sa.Column("project_type", sa.String, nullable=False, index=True),
        sa.Column("project_address", sa.String, nullable=True),
        sa.Column("parcel_loc_id", sa.String, sa.ForeignKey("parcels.loc_id"), nullable=True),
        sa.Column("applicant", sa.String, nullable=True),
        sa.Column("decision", sa.String, index=True, nullable=True),
        sa.Column("conditions", ARRAY(sa.Text), nullable=True),
        sa.Column("filing_date", sa.Date, nullable=True),
        sa.Column("decision_date", sa.Date, nullable=True),
        sa.Column("meeting_body", sa.String, nullable=True),
        sa.Column("source_url", sa.String, nullable=False),
        sa.Column("full_text", sa.Text, nullable=True),
        sa.Column("confidence", sa.Float, nullable=True),
        sa.Column("embedding", Vector(1024), nullable=True),
        sa.Column(
            "geom",
            Geometry(geometry_type="POINT", srid=SRID, spatial_index=True),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("precedents")
