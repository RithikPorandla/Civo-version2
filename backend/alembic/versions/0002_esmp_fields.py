"""Expand esmp_projects schema for real seed data.

Revision ID: 0002_esmp_fields
Revises: 0001_initial_schema
Create Date: 2026-04-14
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002_esmp_fields"
down_revision: Union[str, None] = "0001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()

    op.execute(sa.text("ALTER TABLE esmp_projects ADD COLUMN IF NOT EXISTS municipality VARCHAR"))
    op.execute(sa.text("ALTER TABLE esmp_projects ADD COLUMN IF NOT EXISTS coordinate_confidence VARCHAR"))
    op.execute(sa.text("ALTER TABLE esmp_projects ADD COLUMN IF NOT EXISTS siting_status VARCHAR"))
    op.execute(sa.text("ALTER TABLE esmp_projects ADD COLUMN IF NOT EXISTS source_filing VARCHAR NOT NULL DEFAULT 'DPU 24-10'"))

    if bind.execute(sa.text(
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_name='esmp_projects' AND column_name='source_docket'"
    )).fetchone():
        op.execute(sa.text("ALTER TABLE esmp_projects DROP COLUMN source_docket"))

    op.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_esmp_municipality ON esmp_projects (municipality)"))
    op.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_esmp_siting_status ON esmp_projects (siting_status)"))

    if not bind.execute(sa.text(
        "SELECT 1 FROM pg_constraint WHERE conname='esmp_project_name_uq'"
    )).fetchone():
        op.create_unique_constraint("esmp_project_name_uq", "esmp_projects", ["project_name"])


def downgrade() -> None:
    op.drop_constraint("esmp_project_name_uq", "esmp_projects", type_="unique")
    op.drop_index("ix_esmp_siting_status", table_name="esmp_projects")
    op.drop_index("ix_esmp_municipality", table_name="esmp_projects")
    with op.batch_alter_table("esmp_projects") as b:
        b.add_column(sa.Column("source_docket", sa.String(), server_default="DPU 24-10"))
        b.drop_column("source_filing")
        b.drop_column("siting_status")
        b.drop_column("coordinate_confidence")
        b.drop_column("municipality")
