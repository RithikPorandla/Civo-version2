"""ML feature cache, town sentiment, and aerial image feature tables.

Revision ID: 0012
Revises: 0011
Create Date: 2026-04-23
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    if not bind.execute(sa.text(
        "SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='parcel_ml_features'"
    )).fetchone():
        op.create_table(
            "parcel_ml_features",
            sa.Column("parcel_loc_id", sa.Text, sa.ForeignKey("parcels.loc_id", ondelete="CASCADE"), primary_key=True),
            # Physical geometry
            sa.Column("area_m2", sa.Float),
            sa.Column("shape_index", sa.Float),
            sa.Column("perimeter_m", sa.Float),
            # Constraint coverage fractions (0–1)
            sa.Column("pct_biomap_core", sa.Float, server_default="0"),
            sa.Column("pct_nhesp_priority", sa.Float, server_default="0"),
            sa.Column("pct_nhesp_estimated", sa.Float, server_default="0"),
            sa.Column("pct_flood_zone", sa.Float, server_default="0"),
            sa.Column("pct_wetlands", sa.Float, server_default="0"),
            sa.Column("pct_article97", sa.Float, server_default="0"),
            sa.Column("pct_prime_farmland", sa.Float, server_default="0"),
            # Grid proximity
            sa.Column("dist_to_esmp_m", sa.Float),
            sa.Column("nearest_esmp_mw", sa.Float),
            sa.Column("dist_to_hca_m", sa.Float),
            sa.Column("nearest_hca_mw", sa.Float),
            sa.Column("n_esmp_5km", sa.Integer, server_default="0"),
            sa.Column("total_hca_mw_5km", sa.Float, server_default="0"),
            # Jurisdiction signals
            sa.Column("doer_bess_score", sa.Float, server_default="0.5"),
            sa.Column("doer_solar_score", sa.Float, server_default="0.5"),
            sa.Column("moratorium_active", sa.Boolean, server_default="false"),
            sa.Column("concom_approval_rate", sa.Float),
            sa.Column("median_permit_days", sa.Float),
            sa.Column("total_precedents", sa.Integer, server_default="0"),
            sa.Column("risk_multiplier", sa.Float, server_default="1.0"),
            # Spatial neighborhood context
            sa.Column("approved_projects_1km", sa.Integer, server_default="0"),
            sa.Column("denied_projects_1km", sa.Integer, server_default="0"),
            sa.Column("approved_projects_5km", sa.Integer, server_default="0"),
            sa.Column("denied_projects_5km", sa.Integer, server_default="0"),
            sa.Column("avg_neighbor_score_5km", sa.Float),
            sa.Column("n_scored_neighbors_5km", sa.Integer, server_default="0"),
            # Sentiment signals
            sa.Column("town_sentiment_bess", sa.Float),
            sa.Column("town_sentiment_solar", sa.Float),
            # Aerial image features (Layer 3)
            sa.Column("aerial_veg_index", sa.Float),
            sa.Column("aerial_edge_density", sa.Float),
            sa.Column("aerial_mean_brightness", sa.Float),
            sa.Column("aerial_texture_var", sa.Float),
            # ML model outputs
            sa.Column("ml_score_bess", sa.Float),
            sa.Column("ml_score_solar", sa.Float),
            # Timestamps
            sa.Column("extracted_at", sa.DateTime(timezone=True)),
            sa.Column("aerial_at", sa.DateTime(timezone=True)),
            sa.Column("ml_scored_at", sa.DateTime(timezone=True)),
        )
        op.execute(sa.text(
            "CREATE INDEX IF NOT EXISTS ix_parcel_ml_features_extracted ON parcel_ml_features (extracted_at)"
        ))

    if not bind.execute(sa.text(
        "SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='town_sentiment'"
    )).fetchone():
        op.create_table(
            "town_sentiment",
            sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
            sa.Column("town_name", sa.Text, nullable=False),
            sa.Column("project_type", sa.Text, nullable=False),
            sa.Column("sentiment_score", sa.Float),
            sa.Column("support_score", sa.Float),
            sa.Column("opposition_score", sa.Float),
            sa.Column("document_count", sa.Integer, server_default="0"),
            sa.Column("key_concerns", JSONB),
            sa.Column("key_support", JSONB),
            sa.Column("sources", JSONB),
            sa.Column("computed_at", sa.DateTime(timezone=True)),
            sa.UniqueConstraint("town_name", "project_type", name="uq_sentiment_town_pt"),
        )


def downgrade() -> None:
    op.drop_table("town_sentiment")
    op.drop_index("ix_parcel_ml_features_extracted", "parcel_ml_features")
    op.drop_table("parcel_ml_features")
