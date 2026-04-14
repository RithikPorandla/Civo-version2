"""Initial schema: all 14 tables + PostGIS / pgvector extensions.

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-04-13
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

from app.db import Base
from app import models  # noqa: F401  (registers all tables on Base.metadata)

revision: str = "0001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    # Extensions are also ensured by the container's init SQL, but we repeat
    # here so the migration is self-sufficient against any Postgres target.
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
