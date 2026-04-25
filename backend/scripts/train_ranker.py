"""Train LightGBM site ranking model from labeled parcel features.

Training signal: precedents table (decision = approved|denied) joined directly
to parcel_ml_features via parcel_loc_id. Secondary weak signal: town-level
ConCom approval rate applied to all unlinked parcels in that town.

Produces two models (one per project type):
    models/ranker_bess.pkl
    models/ranker_solar.pkl

Plus feature importance report to stdout.

Usage:
    python -m scripts.train_ranker [--min-samples 10] [--dry-run]
"""

from __future__ import annotations

import argparse
import os
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.model_selection import GroupShuffleSplit
from sklearn.preprocessing import StandardScaler
from sqlalchemy import text

sys.path.insert(0, ".")
from app.db import SessionLocal

MODELS_DIR = Path(__file__).parent.parent / "models"
MODELS_DIR.mkdir(exist_ok=True)

try:
    import lightgbm as lgb
except ImportError:
    print("lightgbm not installed. Run: pip install lightgbm")
    sys.exit(1)

# Features used in training. Order matters for the saved scaler.
FEATURE_COLS = [
    # Physical
    "area_m2", "shape_index",
    # Constraint coverage
    "pct_biomap_core", "pct_nhesp_priority", "pct_nhesp_estimated",
    "pct_flood_zone", "pct_wetlands", "pct_article97", "pct_prime_farmland",
    # Grid
    "dist_to_esmp_m", "nearest_esmp_mw", "dist_to_hca_m", "nearest_hca_mw",
    "n_esmp_5km", "total_hca_mw_5km",
    # Jurisdiction
    "doer_bess_score", "doer_solar_score",
    "moratorium_active", "concom_approval_rate", "median_permit_days",
    "total_precedents", "risk_multiplier",
    # Neighborhood
    "approved_projects_1km", "denied_projects_1km",
    "approved_projects_5km", "denied_projects_5km",
    "avg_neighbor_score_5km", "n_scored_neighbors_5km",
    # Sentiment
    "town_sentiment_bess", "town_sentiment_solar",
]


def _load_data(project_type: str) -> pd.DataFrame:
    """Load features + labels. Direct parcel labels take priority over town-level."""
    doer_col = "doer_bess" if "bess" in project_type else "doer_solar"

    with SessionLocal() as session:
        # Direct labels: parcels with a linked precedent decision
        direct = pd.DataFrame(session.execute(text(f"""
            SELECT
                f.*,
                p.decision,
                'direct'                            AS label_source,
                CONCAT(m.town_name, '_{project_type}') AS query_group
            FROM parcel_ml_features f
            JOIN precedents p ON p.parcel_loc_id = f.parcel_loc_id
            JOIN municipalities m
                ON m.town_name = (
                    SELECT town_name FROM parcels WHERE loc_id = f.parcel_loc_id LIMIT 1
                )
            WHERE p.project_type ILIKE :pt_pattern
              AND p.decision IN ('approved', 'denied')
        """).bindparams(pt_pattern=f"%{doer_col.split('_')[1]}%")).mappings().all())

        # Weak labels: all parcels in towns with precedent data (town approval rate as target)
        weak = pd.DataFrame(session.execute(text("""
            SELECT
                f.*,
                CASE WHEN tjr.concom_approval_rate >= 0.6 THEN 'approved' ELSE 'denied' END AS decision,
                'weak'                                          AS label_source,
                CONCAT(p.town_name, '_', :pt)                  AS query_group
            FROM parcel_ml_features f
            JOIN parcels p ON p.loc_id = f.parcel_loc_id
            JOIN town_jurisdiction_risk tjr
                ON tjr.town_name = p.town_name
               AND tjr.project_type = :pt
            WHERE tjr.total_precedents >= 3
              AND f.parcel_loc_id NOT IN (
                  SELECT pr.parcel_loc_id FROM precedents pr
                  WHERE pr.parcel_loc_id IS NOT NULL
              )
        """), {"pt": project_type}).mappings().all())

    df = pd.concat([direct, weak], ignore_index=True) if not direct.empty else weak
    df = df.drop_duplicates(subset=["parcel_loc_id"])
    return df


def _fill_nulls(df: pd.DataFrame) -> pd.DataFrame:
    fill = {
        "dist_to_esmp_m": 50000,    # 50km → no grid nearby
        "dist_to_hca_m": 50000,
        "nearest_esmp_mw": 0,
        "nearest_hca_mw": 0,
        "concom_approval_rate": 0.5,
        "median_permit_days": 365,
        "avg_neighbor_score_5km": 50.0,
        "town_sentiment_bess": 0.0,
        "town_sentiment_solar": 0.0,
        "moratorium_active": 0,
    }
    return df.fillna(fill)


def train(project_type: str, min_samples: int = 10, dry_run: bool = False) -> None:
    print(f"\n=== Training ranker for {project_type} ===")
    df = _load_data(project_type)
    print(f"  Loaded {len(df)} samples ({len(df[df.decision=='approved'])} approved, "
          f"{len(df[df.decision=='denied'])} denied)")

    if len(df) < min_samples:
        print(f"  Skipping — need at least {min_samples} samples.")
        return

    df = _fill_nulls(df)
    df["label"] = (df["decision"] == "approved").astype(int)
    df["moratorium_active"] = df["moratorium_active"].astype(int)

    X = df[FEATURE_COLS].astype(float)
    y = df["label"]
    groups = df["query_group"]

    # Scale features
    scaler = StandardScaler()
    X_scaled = pd.DataFrame(scaler.fit_transform(X), columns=FEATURE_COLS)

    # Group-aware train/test split (same town stays in same split)
    gss = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=42)
    train_idx, test_idx = next(gss.split(X_scaled, y, groups=groups))

    X_train, X_test = X_scaled.iloc[train_idx], X_scaled.iloc[test_idx]
    y_train, y_test = y.iloc[train_idx], y.iloc[test_idx]

    if dry_run:
        print(f"  Dry run — would train on {len(X_train)} samples, test on {len(X_test)}")
        return

    model = lgb.LGBMClassifier(
        objective="binary",
        n_estimators=300,
        learning_rate=0.05,
        max_depth=6,
        num_leaves=31,
        min_child_samples=5,
        class_weight="balanced",
        random_state=42,
        verbose=-1,
    )
    model.fit(
        X_train, y_train,
        eval_set=[(X_test, y_test)],
        callbacks=[lgb.early_stopping(30, verbose=False), lgb.log_evaluation(50)],
    )

    # Evaluation
    from sklearn.metrics import classification_report, roc_auc_score
    y_prob = model.predict_proba(X_test)[:, 1]
    y_pred = (y_prob >= 0.5).astype(int)
    auc = roc_auc_score(y_test, y_prob) if len(np.unique(y_test)) > 1 else float("nan")
    print(f"\n  Test AUC: {auc:.3f}")
    print(classification_report(y_test, y_pred, target_names=["denied", "approved"]))

    # Feature importance
    importance = sorted(
        zip(FEATURE_COLS, model.feature_importances_),
        key=lambda x: -x[1],
    )
    print("\n  Top 15 features:")
    for feat, imp in importance[:15]:
        bar = "█" * int(imp / max(i for _, i in importance) * 20)
        print(f"    {feat:<35} {bar} {imp:.0f}")

    # Save
    suffix = "bess" if "bess" in project_type else "solar"
    model_path = MODELS_DIR / f"ranker_{suffix}.pkl"
    scaler_path = MODELS_DIR / f"scaler_{suffix}.pkl"
    with open(model_path, "wb") as f:
        pickle.dump(model, f)
    with open(scaler_path, "wb") as f:
        pickle.dump(scaler, f)
    print(f"\n  Model saved → {model_path}")
    print(f"  Scaler saved → {scaler_path}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--min-samples", type=int, default=10)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    for pt in ["bess_standalone", "solar_ground_mount"]:
        train(pt, min_samples=args.min_samples, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
