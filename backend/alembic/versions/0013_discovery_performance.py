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
    op.execute(sa.text("CREATE INDEX IF NOT EXISTS idx_parcels_town_area ON parcels (town_name, shape_area)"))
    op.execute(sa.text("CREATE INDEX IF NOT EXISTS idx_score_history_parcel ON score_history (parcel_loc_id, computed_at DESC)"))
    op.execute(sa.text("CREATE INDEX IF NOT EXISTS idx_parcels_use_code ON parcels (use_code)"))

    op.execute(sa.text("ALTER TABLE parcels ADD COLUMN IF NOT EXISTS flag_biomap_core BOOLEAN"))
    op.execute(sa.text("ALTER TABLE parcels ADD COLUMN IF NOT EXISTS flag_nhesp_priority BOOLEAN"))
    op.execute(sa.text("ALTER TABLE parcels ADD COLUMN IF NOT EXISTS flag_flood_zone BOOLEAN"))
    op.execute(sa.text("ALTER TABLE parcels ADD COLUMN IF NOT EXISTS flag_wetlands BOOLEAN"))
    op.execute(sa.text("ALTER TABLE parcels ADD COLUMN IF NOT EXISTS flag_article97 BOOLEAN"))
    op.execute(sa.text("ALTER TABLE parcels ADD COLUMN IF NOT EXISTS flag_prime_farmland BOOLEAN"))
    op.execute(sa.text("ALTER TABLE parcels ADD COLUMN IF NOT EXISTS flags_computed_at TIMESTAMPTZ"))


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
