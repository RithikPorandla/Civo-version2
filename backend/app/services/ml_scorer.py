"""ML scoring service — loads trained LightGBM models and scores parcels.

Models live at models/ranker_{bess,solar}.pkl (trained by scripts/train_ranker.py).
Falls back gracefully to None if models aren't present — discovery engine uses
rule-based score in that case.

Blended score formula:
    effective_score = (rule_score / 100) * risk_multiplier

ML weight is set to 0 — scoring is fully rule-based using the YAML config
criteria weights. ML models are still loaded if present but have no influence
on the output score.
"""

from __future__ import annotations

import pickle
from pathlib import Path
from typing import Any

import numpy as np

MODELS_DIR = Path(__file__).parent.parent.parent / "models"

FEATURE_COLS = [
    "area_m2", "shape_index",
    "pct_biomap_core", "pct_nhesp_priority", "pct_nhesp_estimated",
    "pct_flood_zone", "pct_wetlands", "pct_article97", "pct_prime_farmland",
    "dist_to_esmp_m", "nearest_esmp_mw", "dist_to_hca_m", "nearest_hca_mw",
    "n_esmp_5km", "total_hca_mw_5km",
    "doer_bess_score", "doer_solar_score",
    "moratorium_active", "concom_approval_rate", "median_permit_days",
    "total_precedents", "risk_multiplier",
    "approved_projects_1km", "denied_projects_1km",
    "approved_projects_5km", "denied_projects_5km",
    "avg_neighbor_score_5km", "n_scored_neighbors_5km",
    "town_sentiment_bess", "town_sentiment_solar",
]

FEATURE_DEFAULTS = {
    "dist_to_esmp_m": 50000,
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

_ML_WEIGHT = 0.0
_RULE_WEIGHT = 1.0


class _ModelPair:
    """Lazy-loaded (model, scaler) pair for one project type."""

    def __init__(self, suffix: str) -> None:
        self._suffix = suffix
        self._model = None
        self._scaler = None
        self._loaded = False

    def _load(self) -> None:
        if self._loaded:
            return
        self._loaded = True
        model_path = MODELS_DIR / f"ranker_{self._suffix}.pkl"
        scaler_path = MODELS_DIR / f"scaler_{self._suffix}.pkl"
        if model_path.exists() and scaler_path.exists():
            with open(model_path, "rb") as f:
                self._model = pickle.load(f)
            with open(scaler_path, "rb") as f:
                self._scaler = pickle.load(f)

    @property
    def available(self) -> bool:
        self._load()
        return self._model is not None

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        self._load()
        if self._model is None:
            return np.full(len(X), 0.5)
        X_scaled = self._scaler.transform(X)
        return self._model.predict_proba(X_scaled)[:, 1]


_MODELS: dict[str, _ModelPair] = {
    "bess_standalone": _ModelPair("bess"),
    "bess_colocated": _ModelPair("bess"),
    "solar_ground_mount": _ModelPair("solar"),
    "solar_canopy": _ModelPair("solar"),
    "solar_rooftop": _ModelPair("solar"),
}


def model_available(project_type: str | None) -> bool:
    if not project_type:
        return False
    pair = _MODELS.get(project_type)
    return pair is not None and pair.available


def blend_scores(
    results: list[dict[str, Any]],
    ml_features: dict[str, dict[str, Any]],
    project_type: str | None,
) -> list[dict[str, Any]]:
    """Inject ml_score and blended_score into each result dict in-place.

    `ml_features`: mapping of parcel_id → feature dict from parcel_ml_features.
    Parcels without ML features fall back to rule-based score only.
    """
    if not project_type or not model_available(project_type):
        for r in results:
            r["ml_score"] = None
            r["blended_score"] = (r.get("total_score") or 0) * (r.get("risk_multiplier") or 1.0)
        return results

    pair = _MODELS[project_type]

    # Build feature matrix in one shot
    rows_with_feats = []
    indices_with_feats = []
    for i, r in enumerate(results):
        feats = ml_features.get(r["parcel_id"])
        if feats:
            rows_with_feats.append(feats)
            indices_with_feats.append(i)

    if rows_with_feats:
        X = np.array([
            [float(_get_feat(row, col)) for col in FEATURE_COLS]
            for row in rows_with_feats
        ])
        probs = pair.predict_proba(X)

        for i, prob in zip(indices_with_feats, probs):
            r = results[i]
            rule = (r.get("total_score") or 0) / 100.0
            risk = r.get("risk_multiplier") or 1.0
            r["ml_score"] = round(float(prob) * 100, 1)
            r["blended_score"] = round(
                (_ML_WEIGHT * float(prob) + _RULE_WEIGHT * rule * risk) * 100, 1
            )

    # Fill missing
    for r in results:
        if "ml_score" not in r:
            r["ml_score"] = None
            r["blended_score"] = (r.get("total_score") or 0) * (r.get("risk_multiplier") or 1.0)

    return results


def _get_feat(row: dict[str, Any], col: str) -> float:
    val = row.get(col)
    if val is None:
        val = FEATURE_DEFAULTS.get(col, 0.0)
    if isinstance(val, bool):
        return float(val)
    try:
        return float(val)
    except (TypeError, ValueError):
        return FEATURE_DEFAULTS.get(col, 0.0)
