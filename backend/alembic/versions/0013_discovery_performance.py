"""Discovery performance: indexes + pre-computed constraint flags on parcels.

Critical indexes:
  idx_parcels_town_area     — eliminates seq scan on town_name + shape_area filter
  idx_score_history_parcel  — eliminates 994-loop inner seq scan on score_history
  idx_parcels_use_code      — enables fast land-use pre-filtering

Pre-computed flag columns (populated by scripts/precompute_flags.py):
  flag_biomap_core, flag_nhesp_priority, flag_flood_zone,
  flag_wetlands, flag_article97, flag_prime_farmland
  flags_computed_at — NULL = not yet computed; discovery falls back to LATERAL

Revision ID: 0013
Revises: 0012
Create Date: 2026-04-23
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Critical query indexes ────────────────────────────────────────────────

    # Eliminates full sequential scan on parcels (was reading 206k rows to find ~1k)
    op.create_index("idx_parcels_town_area", "parcels", ["town_name", "shape_area"])

    # Eliminates 994-loop inner seq scan — single most impactful change
    op.create_index("idx_score_history_parcel", "score_history", ["parcel_loc_id", sa.text("computed_at DESC")])

    # Land use pre-filter
    op.create_index("idx_parcels_use_code", "parcels", ["use_code"])

    # ── Pre-computed constraint flag columns ──────────────────────────────────
    op.add_column("parcels", sa.Column("flag_biomap_core",    sa.Boolean, nullable=True))
    op.add_column("parcels", sa.Column("flag_nhesp_priority", sa.Boolean, nullable=True))
    op.add_column("parcels", sa.Column("flag_flood_zone",     sa.Boolean, nullable=True))
    op.add_column("parcels", sa.Column("flag_wetlands",       sa.Boolean, nullable=True))
    op.add_column("parcels", sa.Column("flag_article97",      sa.Boolean, nullable=True))
    op.add_column("parcels", sa.Column("flag_prime_farmland", sa.Boolean, nullable=True))
    op.add_column("parcels", sa.Column("flags_computed_at",   sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("parcels", "flags_computed_at")
    op.drop_column("parcels", "flag_prime_farmland")
    op.drop_column("parcels", "flag_article97")
    op.drop_column("parcels", "flag_wetlands")
    op.drop_column("parcels", "flag_flood_zone")
    op.drop_column("parcels", "flag_nhesp_priority")
    op.drop_column("parcels", "flag_biomap_core")
    op.drop_index("idx_parcels_use_code", "parcels")
    op.drop_index("idx_score_history_parcel", "score_history")
    op.drop_index("idx_parcels_town_area", "parcels")
