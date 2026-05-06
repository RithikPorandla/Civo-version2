"""Build the interconnection timeline training dataset.

Joins isone_queue + ferc_queue with spatial and regulatory features to
produce a flat feature matrix with survival labels.

Output
------
A CSV at data/interconnection_training.csv with one row per
completed/withdrawn/active queue entry.  Each row has:

  Survival labels (XGBoost AFT format):
    months_lower   — for completed: months to completion
                   — for censored (active/withdrawn): months elapsed so far
    months_upper   — for completed: same as lower (+0)
                   — for censored: +inf (float('inf'))
    event          — 1 = completed (observed), 0 = censored

  Features:
    capacity_mw, log_capacity_mw
    project_type_bess  (1 if bess_standalone, else 0)
    queue_year, queue_month
    state_* one-hot for ISO-NE states
    n_active_at_entry  — queue congestion by project_type at entry date
    mw_active_at_entry — MW congestion by project_type at entry date
    pct_completed_1yr  — fraction of same-type projects that completed within 1yr of their entry
    doer_score         — DOER adoption score for the town/state (MA only)
    moratorium_active  — town moratorium flag (MA only)

Usage:
    python -m scripts.build_interconnection_training [--out data/interconnection_training.csv]
"""

from __future__ import annotations

import sys
import argparse
from datetime import date, datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.db import SessionLocal

TODAY = date.today()


def _load_queue(session) -> pd.DataFrame:
    """Load all solar/BESS rows from both isone_queue and ferc_queue."""
    isone = pd.DataFrame(session.execute(text("""
        SELECT
            queue_id, project_type, capacity_mw,
            queue_date, status, in_service_date,
            NULL::date AS withdrawn_date,
            COALESCE(town_name, county) AS location,
            state
        FROM isone_queue
        WHERE project_type IN ('solar_ground_mount', 'bess_standalone')
          AND queue_date IS NOT NULL
    """)).mappings().all())

    ferc = pd.DataFrame(session.execute(text("""
        SELECT
            queue_id, project_type, capacity_mw,
            queue_date, status, in_service_date,
            withdrawn_date,
            COALESCE(county, state) AS location,
            state
        FROM ferc_queue
        WHERE project_type IN ('solar_ground_mount', 'bess_standalone')
          AND queue_date IS NOT NULL
    """)).mappings().all())

    df = pd.concat([isone, ferc], ignore_index=True)
    df["queue_date"]      = pd.to_datetime(df["queue_date"]).dt.date
    df["in_service_date"] = pd.to_datetime(df["in_service_date"], errors="coerce").dt.date
    df["withdrawn_date"]  = pd.to_datetime(df["withdrawn_date"],  errors="coerce").dt.date
    df["capacity_mw"]     = pd.to_numeric(df["capacity_mw"], errors="coerce")
    df["state"]           = df["state"].str.upper().str.strip()
    print(f"  Loaded {len(df)} queue rows ({len(isone)} IRTT + {len(ferc)} FERC)")
    return df


def _add_survival_labels(df: pd.DataFrame) -> pd.DataFrame:
    """Compute months_lower, months_upper, event for each row."""
    rows = []
    for _, r in df.iterrows():
        status = str(r["status"]).lower()
        qdate  = r["queue_date"]

        if status == "completed" and r["in_service_date"]:
            # Observed event — both bounds equal the actual duration
            months = (r["in_service_date"] - qdate).days / 30.44
            if months <= 0:
                continue  # data quality issue
            rows.append({**r, "months_lower": months, "months_upper": months, "event": 1})

        elif status in ("active",):
            # Right-censored at today
            months_elapsed = (TODAY - qdate).days / 30.44
            if months_elapsed < 1:
                continue
            rows.append({**r, "months_lower": months_elapsed,
                         "months_upper": float("inf"), "event": 0})

        elif status == "withdrawn":
            end_date = r["withdrawn_date"] or TODAY
            months_elapsed = (end_date - qdate).days / 30.44
            if months_elapsed < 1:
                continue
            # Withdrawn projects: censored at withdrawal — they didn't complete
            # but we can use the elapsed time as a lower bound
            rows.append({**r, "months_lower": months_elapsed,
                         "months_upper": float("inf"), "event": 0})

        # suspended: skip — ambiguous status

    result = pd.DataFrame(rows)
    print(f"  After label assignment: {len(result)} rows "
          f"({result['event'].sum():.0f} completed, "
          f"{(result['event']==0).sum():.0f} censored)")
    return result


def _add_congestion_features(df: pd.DataFrame) -> pd.DataFrame:
    """For each project, count how many same-type projects were active in ISO-NE
    when this one entered the queue — proxy for system-level congestion.
    """
    df = df.sort_values("queue_date").reset_index(drop=True)
    df["n_active_at_entry"] = 0.0
    df["mw_active_at_entry"] = 0.0

    for ptype in df["project_type"].unique():
        mask = df["project_type"] == ptype
        sub  = df[mask].copy()

        for idx in sub.index:
            qdate = sub.at[idx, "queue_date"]
            end_dates = sub["in_service_date"].fillna(TODAY)
            # Projects that entered before this one and were still active
            prior_mask = (sub["queue_date"] < qdate) & (end_dates >= qdate)
            df.at[idx, "n_active_at_entry"]  = prior_mask.sum()
            df.at[idx, "mw_active_at_entry"] = sub.loc[prior_mask, "capacity_mw"].sum()

    return df


def _add_historical_completion_rate(df: pd.DataFrame) -> pd.DataFrame:
    """For each project, compute the fraction of same-type projects that
    completed (as of 2 years after this project's queue date) that
    completed within 24 months — a 'market velocity' signal.
    """
    df = df.sort_values("queue_date").reset_index(drop=True)
    df["pct_completed_24mo"] = 0.5  # default

    for ptype in df["project_type"].unique():
        mask = df["project_type"] == ptype
        sub  = df[mask]

        for idx in sub.index:
            qdate = sub.at[idx, "queue_date"]
            window_start = date(max(qdate.year - 3, 2000), 1, 1)
            window_mask  = (sub["queue_date"] >= window_start) & (sub["queue_date"] < qdate)
            window_df    = sub[window_mask]
            if len(window_df) < 5:
                continue
            completed_fast = (
                (window_df["event"] == 1) &
                (window_df["months_lower"] <= 24)
            ).sum()
            df.at[idx, "pct_completed_24mo"] = completed_fast / len(window_df)

    return df


def _add_regulatory_features(df: pd.DataFrame, session) -> pd.DataFrame:
    """Join DOER adoption score and moratorium flag for MA rows."""
    ma_towns = pd.DataFrame(session.execute(text("""
        SELECT
            m.town_name,
            COALESCE(tjr.risk_multiplier, 1.0)       AS risk_multiplier,
            COALESCE(tjr.moratorium_active, false)    AS moratorium_active,
            COALESCE((
                SELECT MAX(CASE WHEN mda.adoption_status = 'adopted' THEN 1.0
                                WHEN mda.adoption_status = 'in_progress' THEN 0.5
                                ELSE 0.0 END)
                FROM municipal_doer_adoption mda
                WHERE mda.municipality_id = m.town_id
            ), 0.0) AS doer_score
        FROM municipalities m
        LEFT JOIN town_jurisdiction_risk tjr
            ON tjr.town_name = m.town_name
    """)).mappings().all())

    if ma_towns.empty:
        df["risk_multiplier"]  = 1.0
        df["moratorium_active"] = 0
        df["doer_score"]        = 0.0
        return df

    ma_towns["town_name"] = ma_towns["town_name"].str.upper().str.strip()
    df["_location_upper"] = df["location"].str.upper().str.strip()
    df = df.merge(ma_towns, left_on="_location_upper", right_on="town_name", how="left")
    df["risk_multiplier"]  = df["risk_multiplier"].fillna(1.0)
    df["moratorium_active"] = df["moratorium_active"].fillna(0).astype(int)
    df["doer_score"]        = df["doer_score"].fillna(0.0)
    df = df.drop(columns=["_location_upper", "town_name"], errors="ignore")
    return df


def _check_hca_available(session) -> bool:
    row = session.execute(text("SELECT COUNT(*) FROM hosting_capacity")).scalar()
    return (row or 0) > 0


def build(out_path: Path) -> pd.DataFrame:
    with SessionLocal() as session:
        print("Loading queue data ...")
        df = _load_queue(session)

        print("Computing survival labels ...")
        df = _add_survival_labels(df)

        print("Computing queue congestion features ...")
        df = _add_congestion_features(df)

        print("Computing historical completion rate ...")
        df = _add_historical_completion_rate(df)

        print("Joining regulatory features ...")
        df = _add_regulatory_features(df, session)

        hca_available = _check_hca_available(session)
        if not hca_available:
            print("  hosting_capacity table empty — HCA features will be imputed as 0")

    # ── Core feature engineering ──────────────────────────────────────────
    df["log_capacity_mw"]     = np.log1p(df["capacity_mw"].fillna(0).clip(lower=0))
    df["project_type_bess"]   = (df["project_type"] == "bess_standalone").astype(int)
    df["queue_year"]          = pd.to_datetime(df["queue_date"]).dt.year
    df["queue_month"]         = pd.to_datetime(df["queue_date"]).dt.month
    df["years_since_2010"]    = (df["queue_year"] - 2010).clip(lower=0)  # trend feature

    # State one-hot (ISO-NE states)
    for state in ("MA", "CT", "RI", "NH", "VT", "ME"):
        df[f"state_{state}"] = (df["state"] == state).astype(int)

    # Normalize congestion
    df["n_active_at_entry"]  = df["n_active_at_entry"].fillna(0)
    df["mw_active_at_entry"] = df["mw_active_at_entry"].fillna(0)
    df["log_mw_congestion"]  = np.log1p(df["mw_active_at_entry"])
    df["pct_completed_24mo"] = df["pct_completed_24mo"].fillna(0.5)

    # HCA feature placeholder (0 when not available)
    df["nearest_hca_mw"] = 0.0

    # Select final columns
    feature_cols = [
        "queue_id", "project_type", "state",
        # survival labels
        "months_lower", "months_upper", "event",
        # features
        "log_capacity_mw", "project_type_bess",
        "queue_year", "queue_month", "years_since_2010",
        "state_MA", "state_CT", "state_RI", "state_NH", "state_VT", "state_ME",
        "n_active_at_entry", "log_mw_congestion",
        "pct_completed_24mo",
        "doer_score", "moratorium_active", "risk_multiplier",
        "nearest_hca_mw",
    ]
    df = df[[c for c in feature_cols if c in df.columns]].copy()

    # Drop rows missing key features
    df = df.dropna(subset=["months_lower", "log_capacity_mw"])

    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, index=False)

    completed = df["event"].sum()
    censored  = (df["event"] == 0).sum()
    print(f"\nTraining set: {len(df)} rows — {completed:.0f} completed, {censored:.0f} censored")
    print(f"  Completed median: {df[df['event']==1]['months_lower'].median():.1f} months")
    print(f"  Saved to {out_path}")
    return df


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", default="data/interconnection_training.csv")
    args = parser.parse_args()
    build(Path(args.out))


if __name__ == "__main__":
    main()
