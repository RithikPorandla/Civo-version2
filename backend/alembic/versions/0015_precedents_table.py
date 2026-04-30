"""Create precedents table (was missing from initial schema migration).

Revision ID: 0015_precedents_table
Revises: 0014
Create Date: 2026-04-29
"""
from __future__ import annotations

from alembic import op

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Ensure extensions exist — Railway Postgres may not have run migration 0001
    # on this specific DB instance, so we re-create them here idempotently.
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    op.execute("""
        CREATE TABLE IF NOT EXISTS precedents (
            id              SERIAL PRIMARY KEY,
            town_id         INTEGER REFERENCES municipalities(town_id),
            docket          VARCHAR,
            project_type    VARCHAR NOT NULL,
            project_address VARCHAR,
            parcel_loc_id   VARCHAR REFERENCES parcels(loc_id),
            applicant       VARCHAR,
            decision        VARCHAR,
            conditions      TEXT[],
            filing_date     DATE,
            decision_date   DATE,
            meeting_body    VARCHAR,
            source_url      VARCHAR NOT NULL,
            full_text       TEXT,
            confidence      FLOAT,
            embedding       vector(1024),
            geom            geometry(POINT, 26986),
            created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_precedents_town_id ON precedents (town_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_precedents_docket ON precedents (docket)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_precedents_project_type ON precedents (project_type)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_precedents_decision ON precedents (decision)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_precedents_geom ON precedents USING GIST (geom)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS precedents")
