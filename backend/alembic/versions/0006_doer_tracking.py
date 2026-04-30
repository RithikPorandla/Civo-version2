"""Add DOER Model Bylaw tracking.

Two new tables:
  - doer_model_bylaws: canonical DOER Solar + BESS model bylaws, parsed
    from the October 2025 PDFs via Claude vision. Keyed by
    (state, project_type, version).
  - municipal_doer_adoption: per-town adoption status for solar and BESS,
    with version reference so we can detect stale adoptions when DOER
    ships a revised draft. UNIQUE(municipality_id, project_type).

Three JSONB columns on municipalities track the computed diff of the
town's existing project_type_bylaws against the active DOER model:
  - doer_model_aligned: {"solar": bool, "bess": bool}
  - doer_deviation_count: {"solar": int, "bess": int}
  - doer_deviation_details: {"solar": [...], "bess": [...]}

Initial seed loads both parsed JSONs from data/processed/doer/ into
doer_model_bylaws so the comparison engine has a canonical reference
from day one.

Revision ID: 0006_doer_tracking
Revises: 0005_project_type_bylaws
Create Date: 2026-04-16
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0006_doer_tracking"
down_revision: Union[str, None] = "0005_project_type_bylaws"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Path resolution: the alembic process runs from v2/backend/ (see alembic.ini
# prepend_sys_path); the processed JSON lives two levels up.
DOER_JSON_DIR = Path(__file__).resolve().parents[3] / "data" / "processed" / "doer"


def upgrade() -> None:
    bind = op.get_bind()

    # -------------------------------------------------------------------
    # doer_model_bylaws — canonical reference documents
    # -------------------------------------------------------------------
    if not bind.execute(sa.text(
        "SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='doer_model_bylaws'"
    )).fetchone():
        op.create_table(
            "doer_model_bylaws",
            sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
            sa.Column("state", sa.Text, nullable=False, server_default="MA"),
            sa.Column("project_type", sa.Text, nullable=False),
            sa.Column("version", sa.Text, nullable=False),
            sa.Column("parsed_data", JSONB, nullable=False),
            sa.Column("source_url", sa.Text, nullable=False),
            sa.Column("source_pdf_hash", sa.Text, nullable=False),
            sa.Column(
                "parsed_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.UniqueConstraint("state", "project_type", "version", name="uq_doer_model_bylaws"),
        )
        op.create_check_constraint(
            "ck_doer_model_bylaws_project_type",
            "doer_model_bylaws",
            "project_type IN ('solar', 'bess')",
        )

    # -------------------------------------------------------------------
    # municipal_doer_adoption — one row per (town, project_type)
    # -------------------------------------------------------------------
    if not bind.execute(sa.text(
        "SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='municipal_doer_adoption'"
    )).fetchone():
        op.create_table(
            "municipal_doer_adoption",
            sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
            sa.Column("state", sa.Text, nullable=False, server_default="MA"),
            sa.Column(
                "municipality_id",
                sa.Integer,
                sa.ForeignKey("municipalities.town_id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("project_type", sa.Text, nullable=False),
            sa.Column("adoption_status", sa.Text, nullable=False),
            sa.Column("adopted_date", sa.Date, nullable=True),
            sa.Column("town_meeting_article", sa.Text, nullable=True),
            sa.Column("local_modifications", JSONB, nullable=True),
            sa.Column("modification_summary", sa.Text, nullable=True),
            sa.Column("current_local_bylaw_url", sa.Text, nullable=True),
            sa.Column("doer_circuit_rider", sa.Text, nullable=True),
            sa.Column("doer_version_ref", sa.Text, nullable=True),
            sa.Column("source_url", sa.Text, nullable=False),
            sa.Column("source_type", sa.Text, nullable=False),
            sa.Column("confidence", sa.Numeric, nullable=True),
            sa.Column(
                "extracted_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.Column(
                "reviewed_by_human",
                sa.Boolean,
                nullable=False,
                server_default=sa.text("false"),
            ),
            sa.UniqueConstraint(
                "municipality_id", "project_type", name="uq_municipal_doer_adoption"
            ),
        )
        op.create_check_constraint(
            "ck_mda_project_type",
            "municipal_doer_adoption",
            "project_type IN ('solar', 'bess')",
        )
        op.create_check_constraint(
            "ck_mda_adoption_status",
            "municipal_doer_adoption",
            "adoption_status IN ('adopted', 'in_progress', 'not_started', 'unknown')",
        )
        op.create_check_constraint(
            "ck_mda_source_type",
            "municipal_doer_adoption",
            "source_type IN ('town_website', 'town_meeting_warrant', 'agent_extraction', 'manual_entry')",
        )
        op.create_check_constraint(
            "ck_mda_confidence",
            "municipal_doer_adoption",
            "confidence IS NULL OR (confidence BETWEEN 0 AND 1)",
        )
        op.create_index(
            "ix_mda_state_status",
            "municipal_doer_adoption",
            ["state", "adoption_status"],
        )

    # -------------------------------------------------------------------
    # municipalities: DOER alignment cache columns
    # -------------------------------------------------------------------
    op.execute(sa.text("ALTER TABLE municipalities ADD COLUMN IF NOT EXISTS doer_model_aligned JSONB"))
    op.execute(sa.text("ALTER TABLE municipalities ADD COLUMN IF NOT EXISTS doer_deviation_count JSONB"))
    op.execute(sa.text("ALTER TABLE municipalities ADD COLUMN IF NOT EXISTS doer_deviation_details JSONB"))

    # -------------------------------------------------------------------
    # Seed canonical DOER bylaws from parsed JSON
    # -------------------------------------------------------------------
    _seed_doer_model_bylaws()


def _seed_doer_model_bylaws() -> None:
    """Bulk-insert both parsed DOER bylaws into doer_model_bylaws.

    Safe to call on an empty table only; run after the UNIQUE constraint
    is in place so duplicate versions error out deterministically rather
    than silently duplicating rows.
    """
    rows = []
    for project_type in ("solar", "bess"):
        p = DOER_JSON_DIR / f"{project_type}_model_bylaw.json"
        if not p.exists():
            print(
                f"[0006] skip seed: {p} missing — run scripts.parse_doer_bylaws first"
            )
            continue
        payload = json.loads(p.read_text())
        data = payload["data"]
        src = payload["source"]
        rows.append(
            {
                "state": "MA",
                "project_type": project_type,
                "version": data.get("version") or "October 2025 Draft",
                "parsed_data": json.dumps(data),
                "source_url": src["url"],
                "source_pdf_hash": src["sha256"],
                "parsed_at": datetime.now(timezone.utc),
            }
        )

    if not rows:
        return

    conn = op.get_bind()
    conn.execute(
        sa.text(
            """
            INSERT INTO doer_model_bylaws
                (state, project_type, version, parsed_data, source_url,
                 source_pdf_hash, parsed_at)
            VALUES
                (:state, :project_type, :version, CAST(:parsed_data AS jsonb),
                 :source_url, :source_pdf_hash, :parsed_at)
            ON CONFLICT (state, project_type, version) DO NOTHING
            """
        ),
        rows,
    )


def downgrade() -> None:
    op.drop_column("municipalities", "doer_deviation_details")
    op.drop_column("municipalities", "doer_deviation_count")
    op.drop_column("municipalities", "doer_model_aligned")
    op.drop_index("ix_mda_state_status", table_name="municipal_doer_adoption")
    op.drop_table("municipal_doer_adoption")
    op.drop_table("doer_model_bylaws")
