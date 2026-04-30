"""Add project_type_bylaws to municipalities.

Keyed by project type code:
  solar_ground_mount | bess | substation | wind | transmission

Each value is a JSONB blob with the shape:
  {
    "approval_authority": "Planning Board",
    "process": "site_plan_review",
    "estimated_timeline_months": [4, 9],
    "key_triggers": [{"description": "...", "bylaw_ref": "...", "source_url": "..."}],
    "setbacks_ft": {"front": 50, "side": 30, "rear": 30},
    "acreage_cap": 10,
    "overlay_districts": ["Ground-Mounted Solar Overlay"],
    "notes": "...",
    "citations": [{"source_url": "...", "retrieved_at": "...", "document_title": "..."}]
  }

The column is JSONB so we can evolve per-project-type schemas without
needing another migration — the app layer validates shape via Pydantic.

Revision ID: 0005_project_type_bylaws
Revises: 0004_portfolios
Create Date: 2026-04-14
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0005_project_type_bylaws"
down_revision: Union[str, None] = "0004_portfolios"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(sa.text(
        "ALTER TABLE municipalities ADD COLUMN IF NOT EXISTS "
        "project_type_bylaws JSONB NOT NULL DEFAULT '{}'::jsonb"
    ))


def downgrade() -> None:
    op.drop_column("municipalities", "project_type_bylaws")
