"""Add link_health cache for citation URL health.

Gov URLs (mass.gov, MassGIS, malegislature.gov) rot unpredictably when
upstream restructures slugs. This table caches the last-known status
for every URL Civo emits, so the API can enrich citations with a
``healthy / archived / broken`` indicator and a Wayback Machine fallback
without a live HEAD-probe on every request.

Refresh policy lives in ``services.link_health``: a URL is re-checked
if its row is stale (>24h) or missing. The table is append-only from
the app's point of view (we UPSERT on the URL primary key).

Revision ID: 0007_link_health
Revises: 0006_doer_tracking
Create Date: 2026-04-16
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0007_link_health"
down_revision: Union[str, None] = "0006_doer_tracking"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.execute(sa.text(
        "SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='link_health'"
    )).fetchone():
        return

    op.create_table(
        "link_health",
        sa.Column("url", sa.Text, primary_key=True),
        sa.Column("status_code", sa.Integer, nullable=True),
        sa.Column("healthy", sa.Boolean, nullable=False),
        sa.Column("final_url", sa.Text, nullable=True),
        sa.Column("wayback_url", sa.Text, nullable=True),
        sa.Column(
            "checked_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "consecutive_failures",
            sa.Integer,
            server_default=sa.text("0"),
            nullable=False,
        ),
    )
    op.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_link_health_healthy ON link_health (healthy)"))


def downgrade() -> None:
    op.drop_index("ix_link_health_healthy", table_name="link_health")
    op.drop_table("link_health")
