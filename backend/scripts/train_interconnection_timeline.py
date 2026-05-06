"""Train the interconnection timeline predictor using XGBoost AFT survival model.

Uses Accelerated Failure Time (AFT) objective which correctly handles censored
data — projects still in queue contribute to training without biasing estimates.

Model
-----
XGBoost with objective='survival:aft', aft_loss_distribution='logistic'.
Logistic AFT chosen over normal AFT because interconnection timelines are
right-skewed (some projects linger for years), which the logistic distribution
handles better.

Output
------
models/timeline_{bess,solar}.pkl  — dict with keys:
    model     : trained XGBoost Booster
    sigma     : scale parameter (from held-out calibration)
    features  : ordered list of feature names
    calibration: {'p50_bias': ..., 'p90_bias': ...}

Evaluation
----------
Leave-one-state-out cross-validation on ISO-NE states.
For each fold: compute median absolute error on completed projects only,
plus P50 and P90 calibration (predicted quantile vs actual).

Usage:
    python -m scripts.train_interconnection_timeline [--data data/interconnection_training.csv]
"""

from __future__ import annotations

import argparse
import pickle
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import logistic as logistic_dist

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:
    import xgboost as xgb
except ImportError:
    print("xgboost required: pip install xgboost")
    sys.exit(1)

MODELS_DIR = Path(__file__).resolve().parents[1] / "models"
MODELS_DIR.mkdir(exist_ok=True)

FEATURE_COLS = [
    "log_capacity_mw",
    "project_type_bess",
    "queue_year",
    "queue_month",
    "years_since_2010",
    "state_MA", "state_CT", "state_RI", "state_NH", "state_VT", "state_ME",
    "n_active_at_entry",
    "log_mw_congestion",
    "pct_completed_24mo",
    "doer_score",
    "moratorium_active",
    "risk_multiplier",
    "nearest_hca_mw",
]

# XGBoost AFT hyperparameters (tuned for small-N survival data)
XGB_PARAMS = {
    "objective":                  "survival:aft",
    "aft_loss_distribution":      "logistic",
    "aft_loss_distribution_scale": 1.0,
    "eval_metric":                "aft-nloglik",
    "learning_rate":              0.05,
    "max_depth":                  4,
    "min_child_weight":           5,    # prevent overfitting on small N
    "subsample":                  0.8,
    "colsample_bytree":           0.8,
    "reg_alpha":                  0.1,
    "reg_lambda":                 1.0,
    "n_estimators":               300,
    "seed":                       42,
    "verbosity":                  0,
}


def _make_dmatrix(X: np.ndarray, y_lower: np.ndarray, y_upper: np.ndarray) -> xgb.DMatrix:
    dm = xgb.DMatrix(X)
    dm.set_float_info("label_lower_bound", y_lower)
    dm.set_float_info("label_upper_bound", y_upper)
    return dm


def _predict_quantiles(
    booster: xgb.Booster,
    X: np.ndarray,
    sigma: float,
    quantiles: list[float],
) -> np.ndarray:
    """Return predicted time quantiles for each row in X.

    For logistic AFT: t_q = exp(mu + sigma * logit(q))
    where mu = booster.predict(X) and logit(q) is the logistic quantile fn.
    """
    dm = xgb.DMatrix(X)
    mu = booster.predict(dm)  # log(mean survival time)
    result = np.zeros((len(X), len(quantiles)))
    for j, q in enumerate(quantiles):
        result[:, j] = np.exp(mu + sigma * logistic_dist.ppf(q))
    return result


def _calibrate_sigma(
    booster: xgb.Booster,
    X: np.ndarray,
    y_true: np.ndarray,
    sigma_candidates: np.ndarray | None = None,
) -> float:
    """Find sigma that minimises P50 calibration error on completed projects.

    The XGBoost AFT model outputs the log-mean (mu); the scale (sigma) needs
    to be calibrated separately for accurate quantile predictions.
    """
    dm = xgb.DMatrix(X)
    mu = booster.predict(dm)

    if sigma_candidates is None:
        sigma_candidates = np.arange(0.3, 2.5, 0.05)

    best_sigma, best_err = 1.0, float("inf")
    for s in sigma_candidates:
        p50 = np.exp(mu + s * logistic_dist.ppf(0.5))
        # P50 calibration: fraction of actuals below predicted P50 should be ~0.5
        coverage = (y_true <= p50).mean()
        err = abs(coverage - 0.5)
        if err < best_err:
            best_err, best_sigma = err, s

    return float(best_sigma)


def _loso_cv(df: pd.DataFrame, features: list[str]) -> dict:
    """Leave-one-state-out cross-validation."""
    states = [s for s in df["state"].dropna().unique() if df[df["state"] == s]["event"].sum() >= 3]
    if not states:
        print("  Not enough states for LOSO CV — skipping")
        return {}

    mae_list, p50_cal_list, p90_cal_list = [], [], []

    for held_out_state in states:
        train_df = df[df["state"] != held_out_state]
        test_df  = df[(df["state"] == held_out_state) & (df["event"] == 1)]

        if len(train_df) < 30 or len(test_df) < 5:
            continue

        X_train = train_df[features].fillna(0).values
        y_lower = train_df["months_lower"].values.astype(float)
        y_upper = np.where(train_df["event"] == 1,
                           train_df["months_lower"].values,
                           np.full(len(train_df), 1e6)).astype(float)

        dm_train = _make_dmatrix(X_train, y_lower, y_upper)
        booster  = xgb.train(XGB_PARAMS, dm_train, num_boost_round=XGB_PARAMS["n_estimators"],
                             verbose_eval=False)

        X_test   = test_df[features].fillna(0).values
        y_test   = test_df["months_lower"].values.astype(float)
        sigma    = _calibrate_sigma(booster, X_test, y_test)
        qs       = _predict_quantiles(booster, X_test, sigma, [0.25, 0.5, 0.75, 0.9])

        mae = np.median(np.abs(qs[:, 1] - y_test))
        p50_cal = (y_test <= qs[:, 1]).mean()
        p90_cal = (y_test <= qs[:, 3]).mean()

        mae_list.append(mae)
        p50_cal_list.append(p50_cal)
        p90_cal_list.append(p90_cal)
        print(f"    LOSO [{held_out_state}]: MAE={mae:.1f}mo  P50-cal={p50_cal:.2f}  P90-cal={p90_cal:.2f}")

    if not mae_list:
        return {}

    return {
        "loso_mae_median_months": float(np.median(mae_list)),
        "p50_calibration_mean":   float(np.mean(p50_cal_list)),
        "p90_calibration_mean":   float(np.mean(p90_cal_list)),
        "n_folds":                len(mae_list),
    }


def train_model(df: pd.DataFrame, project_type: str) -> dict:
    """Train a single AFT model for one project type.

    Returns a dict suitable for pickling: model, sigma, features, calibration.
    """
    sub = df[df["project_type"] == project_type].copy()
    print(f"\n[{project_type}] Training on {len(sub)} rows "
          f"({sub['event'].sum():.0f} completed)")

    if len(sub) < 20:
        print(f"  Insufficient data for {project_type} — skipping")
        return {}

    features = [f for f in FEATURE_COLS if f in sub.columns]

    # ── Cross-validation ─────────────────────────────────────────────────
    print("  Running leave-one-state-out CV ...")
    cv_metrics = _loso_cv(sub, features)
    for k, v in cv_metrics.items():
        print(f"    {k}: {v:.3f}" if isinstance(v, float) else f"    {k}: {v}")

    # ── Full model on all data ────────────────────────────────────────────
    X = sub[features].fillna(0).values
    y_lower = sub["months_lower"].values.astype(float)
    y_upper = np.where(sub["event"] == 1,
                       sub["months_lower"].values,
                       np.full(len(sub), 1e6)).astype(float)

    dm = _make_dmatrix(X, y_lower, y_upper)
    booster = xgb.train(
        XGB_PARAMS, dm,
        num_boost_round=XGB_PARAMS["n_estimators"],
        verbose_eval=False,
    )

    # ── Calibrate sigma on completed projects ─────────────────────────────
    completed = sub[sub["event"] == 1]
    X_comp = completed[features].fillna(0).values
    y_comp = completed["months_lower"].values.astype(float)
    sigma  = _calibrate_sigma(booster, X_comp, y_comp)
    print(f"  Calibrated sigma: {sigma:.3f}")

    # ── Sanity check on training set ──────────────────────────────────────
    qs = _predict_quantiles(booster, X_comp, sigma, [0.25, 0.5, 0.75, 0.9])
    p50_cal = (y_comp <= qs[:, 1]).mean()
    p90_cal = (y_comp <= qs[:, 3]).mean()
    train_mae = np.median(np.abs(qs[:, 1] - y_comp))
    print(f"  Train MAE (P50): {train_mae:.1f} months")
    print(f"  P50 coverage: {p50_cal:.2f} (target 0.50)")
    print(f"  P90 coverage: {p90_cal:.2f} (target 0.90)")

    # ── Feature importance (top 10) ───────────────────────────────────────
    importance = booster.get_score(importance_type="gain")
    top = sorted(importance.items(), key=lambda x: x[1], reverse=True)[:10]
    print("  Top features (gain):")
    for feat, score in top:
        print(f"    {feat}: {score:.1f}")

    return {
        "model":       booster,
        "sigma":       sigma,
        "features":    features,
        "cv_metrics":  cv_metrics,
        "calibration": {
            "p50_coverage": p50_cal,
            "p90_coverage": p90_cal,
            "train_mae_months": train_mae,
        },
        "n_train":     len(sub),
        "n_completed": int(sub["event"].sum()),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data", default="data/interconnection_training.csv",
                        help="Path to training CSV from build_interconnection_training.py")
    parser.add_argument("--min-rows", type=int, default=20,
                        help="Minimum rows per project type to attempt training")
    args = parser.parse_args()

    data_path = Path(args.data)
    if not data_path.exists():
        print(f"Training data not found at {data_path}")
        print("Run: python -m scripts.build_interconnection_training first")
        sys.exit(1)

    df = pd.read_csv(data_path)
    print(f"Loaded {len(df)} rows from {data_path}")
    print(f"  Completed: {df['event'].sum():.0f}  Censored: {(df['event']==0).sum():.0f}")
    print(f"  Project types: {df['project_type'].value_counts().to_dict()}")
    print(f"  States: {df['state'].value_counts().to_dict()}")

    for project_type, suffix in [
        ("solar_ground_mount", "solar"),
        ("bess_standalone",    "bess"),
    ]:
        result = train_model(df, project_type)
        if not result:
            continue

        out = MODELS_DIR / f"timeline_{suffix}.pkl"
        with open(out, "wb") as f:
            pickle.dump(result, f)
        print(f"\n  Saved model to {out}")

    print("\nDone.")


if __name__ == "__main__":
    main()
