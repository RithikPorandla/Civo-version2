"""Add solar irradiance column and ISO-NE queue table.

Revision ID: 0014_solar_irradiance_isone
Revises: 0013_discovery_performance
Create Date: 2026-04-26
"""
from alembic import op
import sqlalchemy as sa
from geoalchemy2 import Geometry

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Solar irradiance on parcel_ml_features
    op.add_column("parcel_ml_features",
        sa.Column("solar_ghi_kwh_m2_yr", sa.Float(), nullable=True))

    # ISO-NE interconnection queue
    op.create_table(
        "isone_queue",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("queue_id", sa.Text(), unique=True, nullable=False),
        sa.Column("project_name", sa.Text()),
        sa.Column("town_name", sa.Text()),
        sa.Column("county", sa.Text()),
        sa.Column("state", sa.Text(), default="MA"),
        sa.Column("project_type", sa.Text()),   # solar, bess, wind, etc.
        sa.Column("capacity_mw", sa.Float()),
        sa.Column("queue_date", sa.Date()),
        sa.Column("status", sa.Text()),         # active, withdrawn, completed
        sa.Column("in_service_date", sa.Date(), nullable=True),
        sa.Column("geom", Geometry("POINT", srid=26986), nullable=True),
        sa.Column("ingested_at", sa.DateTime(timezone=True)),
    )
    op.create_index("idx_isone_queue_town", "isone_queue", ["town_name"])
    op.create_index("idx_isone_queue_type", "isone_queue", ["project_type"])


def downgrade() -> None:
    op.drop_index("idx_isone_queue_type")
    op.drop_index("idx_isone_queue_town")
    op.drop_table("isone_queue")
    op.drop_column("parcel_ml_features", "solar_ghi_kwh_m2_yr")
