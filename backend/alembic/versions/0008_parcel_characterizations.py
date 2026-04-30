"""Cache table for Claude-vision site characterizations.

Runs once per parcel per vision version. A parcel's characterization
doesn't change every day — the ortho imagery underlying it updates on
MassGIS's multi-year flight cycle — so we cache aggressively and only
re-run when the vision prompt version bumps.

Revision ID: 0008_parcel_characterizations
Revises: 0007_link_health
Create Date: 2026-04-19
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0008_parcel_characterizations"
down_revision: Union[str, None] = "0007_link_health"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.execute(sa.text(
        "SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='parcel_characterizations'"
    )).fetchone():
        return

    op.create_table(
        "parcel_characterizations",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "parcel_loc_id",
            sa.Text,
            sa.ForeignKey("parcels.loc_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("vision_version", sa.Text, nullable=False),
        sa.Column("model_id", sa.Text, nullable=False),
        sa.Column("image_source", sa.Text, nullable=False),
        sa.Column("image_bbox_wgs84", JSONB, nullable=False),
        sa.Column("image_bytes", sa.Integer, nullable=True),
        sa.Column("characterization", JSONB, nullable=False),
        sa.Column("confidence", sa.Numeric, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "parcel_loc_id", "vision_version", name="uq_parcel_char_version"
        ),
    )
    op.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_parcel_char_lookup ON parcel_characterizations (parcel_loc_id, vision_version)"
    ))


def downgrade() -> None:
    op.drop_index("ix_parcel_char_lookup", table_name="parcel_characterizations")
    op.drop_table("parcel_characterizations")
