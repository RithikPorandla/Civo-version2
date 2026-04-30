"""Jurisdiction risk service.

Computes per-town, per-project-type permitting risk multipliers from data
that already exists in the DB (no new scraping required):

  - municipalities.moratoriums  → moratorium_active
  - municipal_doer_adoption     → doer_status
  - precedents GROUP BY         → concom_approval_rate, median_permit_days

The multiplier (0.0–1.0) is applied in the discovery ORDER BY:
  effective_rank = total_score * risk_multiplier

A moratorium town returns 0.0 so its parcels sort to the very bottom.
All other signals apply graduated penalties against a 1.0 baseline.

Call refresh_all() after seeding new precedent or DOER data. Takes ~1s
for 11 towns; safe to run in a background thread on server startup or nightly.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

# Project types we track jurisdiction risk for.
# Extend this list when new project types are scored statewide.
TRACKED_PROJECT_TYPES = [
    "bess_standalone",
    "solar_ground_mount",
]

# DOER adoption → rank penalty (subtract from 1.0 baseline)
_DOER_PENALTY: dict[str | None, float] = {
    "adopted":     0.00,
    "in_progress": 0.05,
    "not_started": 0.15,
    "unknown":     0.00,
    None:          0.00,
}

# Map discovery project_type → DOER project_type column value
_DOER_PROJECT_MAP = {
    "bess_standalone":  "bess",
    "bess_colocated":   "bess",
    "solar_ground_mount": "solar",
    "solar_canopy":     "solar",
    "solar_rooftop":    "solar",
}


def _compute_multiplier(
    moratorium_active: bool,
    doer_status: str | None,
    concom_approval_rate: float | None,
    total_precedents: int,
) -> float:
    if moratorium_active:
        return 0.0

    m = 1.0

    # DOER signal
    m -= _DOER_PENALTY.get(doer_status, 0.0)

    # ConCom approval rate — only meaningful once we have ≥3 decided cases.
    # Maps: approval_rate 1.0 → no penalty; 0.5 → -0.10; 0.0 → -0.20
    if concom_approval_rate is not None and total_precedents >= 3:
        m -= (1.0 - concom_approval_rate) * 0.20

    return round(max(0.05, min(1.0, m)), 4)


def refresh_all(session: Session) -> int:
    """Recompute risk rows for every town in the municipalities table.

    Returns the number of rows upserted. Returns 0 silently if the
    town_jurisdiction_risk table hasn't been created yet (migration 0010).
    Skips precedent-based signals if the precedents table doesn't exist yet
    (migration 0015 / fresh DB with no ingested data).
    """
    table_exists = session.execute(
        text("""
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = 'town_jurisdiction_risk'
            LIMIT 1
        """)
    ).fetchone()
    if not table_exists:
        return 0

    has_precedents = bool(session.execute(
        text("""
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = 'precedents'
            LIMIT 1
        """)
    ).fetchone())

    towns = session.execute(
        text("SELECT town_name FROM municipalities ORDER BY town_name")
    ).scalars().all()

    count = 0
    for town_name in towns:
        for project_type in TRACKED_PROJECT_TYPES:
            _upsert_town_project(session, town_name, project_type, has_precedents)
            count += 1

    session.commit()
    return count


def refresh_town(session: Session, town_name: str) -> None:
    """Recompute risk rows for a single town (all project types)."""
    for project_type in TRACKED_PROJECT_TYPES:
        _upsert_town_project(session, town_name, project_type)
    session.commit()


def _upsert_town_project(session: Session, town_name: str, project_type: str, has_precedents: bool = True) -> None:
    doer_project = _DOER_PROJECT_MAP.get(project_type, "solar")

    # 1. Moratorium flag from municipalities.moratoriums JSONB
    moratorium_row = session.execute(
        text("""
            SELECT moratoriums
            FROM   municipalities
            WHERE  town_name = :town
            LIMIT  1
        """),
        {"town": town_name},
    ).fetchone()

    moratorium_active = False
    if moratorium_row and moratorium_row[0]:
        m = moratorium_row[0]
        # moratoriums JSONB shape: {"bess_standalone": true, "solar_ground_mount": false}
        # or legacy flat: {"active": true}
        if isinstance(m, dict):
            moratorium_active = bool(
                m.get(project_type) or m.get("active") or m.get("all")
            )

    # 2. DOER adoption status
    doer_row = session.execute(
        text("""
            SELECT mda.adoption_status
            FROM   municipal_doer_adoption mda
            JOIN   municipalities m ON m.town_id = mda.municipality_id
            WHERE  m.town_name = :town
              AND  mda.project_type = :doer_pt
            LIMIT  1
        """),
        {"town": town_name, "doer_pt": doer_project},
    ).fetchone()

    doer_status: str | None = doer_row[0] if doer_row else None

    # 3. ConCom/Planning Board approval stats from precedents
    total_precedents = 0
    concom_approval_rate: float | None = None
    median_permit_days: int | None = None

    if has_precedents:
        stats_row = session.execute(
            text("""
                SELECT
                    COUNT(*)                                          AS total,
                    AVG(CASE WHEN decision = 'approved' THEN 1.0
                             WHEN decision = 'denied'   THEN 0.0
                        END)                                          AS approval_rate,
                    PERCENTILE_CONT(0.5) WITHIN GROUP (
                        ORDER BY (decision_date - filing_date)
                    ) FILTER (WHERE decision_date IS NOT NULL
                                AND filing_date  IS NOT NULL)         AS median_days
                FROM  precedents p
                JOIN  municipalities m ON m.town_id = p.town_id
                WHERE m.town_name   = :town
                  AND p.project_type ILIKE :pt_pattern
                  AND p.decision IN ('approved', 'denied')
            """),
            {
                "town": town_name,
                "pt_pattern": "%" + (doer_project) + "%",
            },
        ).fetchone()

        total_precedents = int(stats_row[0]) if stats_row else 0
        concom_approval_rate = float(stats_row[1]) if stats_row and stats_row[1] is not None else None
        median_permit_days = int(stats_row[2]) if stats_row and stats_row[2] is not None else None

    multiplier = _compute_multiplier(
        moratorium_active, doer_status, concom_approval_rate, total_precedents
    )

    session.execute(
        text("""
            INSERT INTO town_jurisdiction_risk
                (town_name, project_type, risk_multiplier, moratorium_active,
                 doer_status, concom_approval_rate, median_permit_days,
                 total_precedents, computed_at)
            VALUES
                (:town, :pt, :mult, :moratorium, :doer_status,
                 :approval_rate, :median_days, :total, :now)
            ON CONFLICT (town_name, project_type) DO UPDATE SET
                risk_multiplier      = EXCLUDED.risk_multiplier,
                moratorium_active    = EXCLUDED.moratorium_active,
                doer_status          = EXCLUDED.doer_status,
                concom_approval_rate = EXCLUDED.concom_approval_rate,
                median_permit_days   = EXCLUDED.median_permit_days,
                total_precedents     = EXCLUDED.total_precedents,
                computed_at          = EXCLUDED.computed_at
        """),
        {
            "town": town_name,
            "pt": project_type,
            "mult": multiplier,
            "moratorium": moratorium_active,
            "doer_status": doer_status,
            "approval_rate": concom_approval_rate,
            "median_days": median_permit_days,
            "total": total_precedents,
            "now": datetime.now(timezone.utc),
        },
    )
