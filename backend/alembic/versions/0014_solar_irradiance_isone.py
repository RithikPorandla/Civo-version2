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
    op.execute(sa.text(
        "ALTER TABLE parcel_ml_features ADD COLUMN IF NOT EXISTS solar_ghi_kwh_m2_yr FLOAT"
    ))

    bind = op.get_bind()
    if bind.execute(sa.text(
        "SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='isone_queue'"
    )).fetchone():
        return

    op.create_table(
        "isone_queue",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("queue_id", sa.Text(), unique=True, nullable=False),
        sa.Column("project_name", sa.Text()),
        sa.Column("town_name", sa.Text()),
        sa.Column("county", sa.Text()),
        sa.Column("state", sa.Text(), default="MA"),
        sa.Column("project_type", sa.Text()),
        sa.Column("capacity_mw", sa.Float()),
        sa.Column("queue_date", sa.Date()),
        sa.Column("status", sa.Text()),
        sa.Column("in_service_date", sa.Date(), nullable=True),
        sa.Column("geom", Geometry("POINT", srid=26986), nullable=True),
        sa.Column("ingested_at", sa.DateTime(timezone=True)),
    )
    op.execute(sa.text("CREATE INDEX IF NOT EXISTS idx_isone_queue_town ON isone_queue (town_name)"))
    op.execute(sa.text("CREATE INDEX IF NOT EXISTS idx_isone_queue_type ON isone_queue (project_type)"))


def downgrade() -> None:
    op.drop_index("idx_isone_queue_type")
    op.drop_index("idx_isone_queue_town")
    op.drop_table("isone_queue")
    op.drop_column("parcel_ml_features", "solar_ghi_kwh_m2_yr")
