"""Interconnection timeline predictor service.

Loads trained XGBoost AFT models (timeline_solar.pkl, timeline_bess.pkl)
and predicts P25/P50/P75/P90 interconnection timelines for a given
parcel + project configuration.

Output format
-------------
{
    "p25_months": 14,
    "p50_months": 22,
    "p75_months": 31,
    "p90_months": 41,
    "confidence": "high" | "medium" | "low",
    "drivers": ["high_capacity", "queue_congestion"],
    "note": "Based on 312 historical ISO-NE solar projects."
}

Confidence tiers
----------------
  high   — model trained on ≥ 200 completed projects of this type
  medium — 50–199 completed projects
  low    — < 50 completed projects (treat as rough estimate)

Falls back gracefully if model files are not present.
"""

from __future__ import annotations

import pickle
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np

MODELS_DIR = Path(__file__).resolve().parents[2] / "models"

_CACHE: dict[str, dict] = {}

_CONFIDENCE_THRESHOLDS = {"high": 200, "medium": 50}

# Current queue congestion — computed once per process start from DB.
# Refreshed lazily on first call.
_CONGESTION_CACHE: dict[str, dict] | None = None


def _load_model(suffix: str) -> dict | None:
    if suffix in _CACHE:
        return _CACHE[suffix]
    path = MODELS_DIR / f"timeline_{suffix}.pkl"
    if not path.exists():
        _CACHE[suffix] = {}
        return None
    with open(path, "rb") as f:
        result = pickle.load(f)
    _CACHE[suffix] = result
    return result


def _get_suffix(project_type: str) -> str:
    if project_type in ("bess_standalone", "bess_colocated"):
        return "bess"
    return "solar"


def _confidence(n_completed: int) -> str:
    if n_completed >= _CONFIDENCE_THRESHOLDS["high"]:
        return "high"
    if n_completed >= _CONFIDENCE_THRESHOLDS["medium"]:
        return "medium"
    return "low"


def _get_congestion(project_type: str, session: Any) -> tuple[float, float]:
    """Return (n_active, total_mw_active) currently in ISO-NE queue."""
    global _CONGESTION_CACHE
    if _CONGESTION_CACHE is None:
        try:
            from sqlalchemy import text
            rows = session.execute(text("""
                SELECT project_type,
                       COUNT(*)        AS n_active,
                       SUM(capacity_mw) AS total_mw
                FROM isone_queue
                WHERE status = 'active'
                GROUP BY project_type
            """)).mappings().all()
            _CONGESTION_CACHE = {
                r["project_type"]: {"n": r["n_active"] or 0, "mw": r["total_mw"] or 0.0}
                for r in rows
            }
        except Exception:
            _CONGESTION_CACHE = {}

    entry = _CONGESTION_CACHE.get(project_type, {})
    return float(entry.get("n", 0)), float(entry.get("mw", 0.0))


def _top_drivers(model_dict: dict, X: np.ndarray) -> list[str]:
    """Return human-readable top 2 factors driving the prediction."""
    booster  = model_dict["model"]
    features = model_dict["features"]

    importance = booster.get_score(importance_type="gain")
    # Map feature name → value for this parcel
    feat_vals = dict(zip(features, X[0]))

    driver_labels = {
        "log_capacity_mw":    "high project capacity" if feat_vals.get("log_capacity_mw", 0) > 3 else "small project (faster)",
        "n_active_at_entry":  "high queue congestion" if feat_vals.get("n_active_at_entry", 0) > 50 else None,
        "log_mw_congestion":  "high MW congestion" if feat_vals.get("log_mw_congestion", 0) > 5 else None,
        "pct_completed_24mo": "low market velocity" if feat_vals.get("pct_completed_24mo", 0.5) < 0.3 else "high market velocity (faster)",
        "doer_score":         "strong DOER alignment (faster)" if feat_vals.get("doer_score", 0) > 0.7 else None,
        "moratorium_active":  "moratorium in effect" if feat_vals.get("moratorium_active", 0) else None,
        "years_since_2010":   "recent vintage" if feat_vals.get("years_since_2010", 0) > 10 else None,
    }

    # Pick top 2 features by importance that have a non-None label
    top = sorted(importance.items(), key=lambda x: x[1], reverse=True)
    result = []
    for feat, _ in top:
        label = driver_labels.get(feat)
        if label:
            result.append(label)
        if len(result) >= 2:
            break
    return result


def predict(
    project_type: str,
    capacity_mw: float,
    queue_year: int | None = None,
    state: str = "MA",
    doer_score: float = 0.0,
    moratorium_active: bool = False,
    risk_multiplier: float = 1.0,
    session: Any = None,
) -> dict[str, Any]:
    """Predict interconnection timeline for a project.

    Parameters
    ----------
    project_type   : 'solar_ground_mount', 'bess_standalone', etc.
    capacity_mw    : project capacity
    queue_year     : year entering queue (defaults to current year)
    state          : ISO-NE state abbreviation
    doer_score     : 0–1 DOER adoption score for the municipality
    moratorium_active : whether a moratorium is in effect
    risk_multiplier: jurisdiction risk multiplier
    session        : SQLAlchemy session (for live congestion lookup)

    Returns
    -------
    dict with p25/p50/p75/p90_months, confidence, drivers, note
    """
    suffix = _get_suffix(project_type)
    m = _load_model(suffix)

    if not m:
        return _fallback(project_type, capacity_mw)

    booster  = m["model"]
    sigma    = m["sigma"]
    features = m["features"]

    if queue_year is None:
        queue_year = date.today().year

    n_active, mw_active = 0.0, 0.0
    if session is not None:
        n_active, mw_active = _get_congestion(project_type, session)

    # Build feature vector matching training schema
    state_feats = {f"state_{s}": int(state.upper() == s) for s in ("MA", "CT", "RI", "NH", "VT", "ME")}

    feat_map: dict[str, float] = {
        "log_capacity_mw":    float(np.log1p(max(capacity_mw, 0))),
        "project_type_bess":  float(suffix == "bess"),
        "queue_year":         float(queue_year),
        "queue_month":        float(date.today().month),
        "years_since_2010":   float(max(queue_year - 2010, 0)),
        "n_active_at_entry":  float(n_active),
        "log_mw_congestion":  float(np.log1p(mw_active)),
        "pct_completed_24mo": 0.5,  # neutral default; no historical data at predict time
        "doer_score":         float(doer_score),
        "moratorium_active":  float(moratorium_active),
        "risk_multiplier":    float(risk_multiplier),
        "nearest_hca_mw":     0.0,
        **{k: float(v) for k, v in state_feats.items()},
    }

    X = np.array([[feat_map.get(f, 0.0) for f in features]])

    # Predict quantiles using logistic AFT formula
    from scipy.stats import logistic as logistic_dist

    dm_pred = __import__("xgboost").DMatrix(X)
    mu = booster.predict(dm_pred)

    quantiles = [0.25, 0.50, 0.75, 0.90]
    q_months  = [float(np.exp(mu[0] + sigma * logistic_dist.ppf(q))) for q in quantiles]

    drivers = _top_drivers(m, X)
    n_completed = m.get("n_completed", 0)

    return {
        "p25_months": round(q_months[0]),
        "p50_months": round(q_months[1]),
        "p75_months": round(q_months[2]),
        "p90_months": round(q_months[3]),
        "confidence": _confidence(n_completed),
        "drivers":    drivers,
        "note": (
            f"Based on {n_completed} completed ISO-NE "
            f"{'BESS' if suffix == 'bess' else 'solar'} interconnection requests."
        ),
    }


def _fallback(project_type: str, capacity_mw: float) -> dict[str, Any]:
    """Heuristic estimates when model file is not present.

    Based on ISO-NE published queue statistics (2022-2024 averages).
    Solar: median ~24mo.  BESS standalone: median ~30mo.
    Larger projects (+100MW) take ~40% longer on average.
    """
    is_bess  = project_type in ("bess_standalone", "bess_colocated")
    base_p50 = 30 if is_bess else 24
    mw_adj   = 1.4 if (capacity_mw or 0) > 100 else 1.0

    p50 = base_p50 * mw_adj
    return {
        "p25_months": round(p50 * 0.65),
        "p50_months": round(p50),
        "p75_months": round(p50 * 1.45),
        "p90_months": round(p50 * 1.9),
        "confidence": "low",
        "drivers":    [],
        "note":       "Model not yet trained — heuristic estimate from ISO-NE queue averages.",
    }


def model_available(project_type: str) -> bool:
    suffix = _get_suffix(project_type)
    return bool(_load_model(suffix))
