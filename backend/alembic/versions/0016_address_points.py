"""address_points: MassGIS Master Address Data lookup table

Stores building-centroid address points from MassGIS MAD (3.7M records statewide).
Used by the resolver as Step 0 — finds the exact building point before geocoding,
eliminating parking-lot / curb-point mismatches.

Each row: parsed address (num + street + town) → WGS84 lat/lon + optional loc_id.
loc_id is populated lazily via a background spatial join (see ingest_address_points.py).
"""

from alembic import op
import sqlalchemy as sa

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE TABLE IF NOT EXISTS address_points (
            id          BIGSERIAL PRIMARY KEY,
            addr_num    INTEGER       NOT NULL,
            addr_suffix TEXT,
            street_name TEXT          NOT NULL,
            unit        TEXT,
            town        TEXT          NOT NULL,
            postcode    TEXT,
            county      TEXT,
            point_type  TEXT,
            lat         DOUBLE PRECISION NOT NULL,
            lon         DOUBLE PRECISION NOT NULL,
            geom        GEOMETRY(POINT, 26986),
            loc_id      TEXT,
            master_address_id BIGINT
        )
    """)

    # Primary resolution index: (number, street, town) → point
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_ap_lookup
            ON address_points (addr_num, street_name, town)
    """)
    # Prefix search on street name for fuzzy matching
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_ap_street_prefix
            ON address_points (town, addr_num, street_name text_pattern_ops)
    """)
    # Spatial index for any geometry-based queries
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_ap_geom
            ON address_points USING GIST (geom)
            WHERE geom IS NOT NULL
    """)
    # Fast loc_id lookup (populated after spatial join)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_ap_loc_id
            ON address_points (loc_id)
            WHERE loc_id IS NOT NULL
    """)
    # Duplicate guard: one canonical point per (num, street, town, unit)
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_ap_unique
            ON address_points (addr_num, street_name, town, COALESCE(unit,''), COALESCE(addr_suffix,''))
    """)


def downgrade():
    op.execute("DROP TABLE IF EXISTS address_points CASCADE")
