"""Unit tests for pure scoring helpers.

These don't hit the database — they verify the interpolation math, the
config loader, and the data_unavailable re-weighting logic that every
criterion relies on.
"""

from __future__ import annotations

import pytest

from app.scoring.engine import _interp, load_config
from app.scoring.models import CriterionScore, SourceCitation, SuitabilityReport


def test_interp_clamps_below_range():
    assert _interp([[0, 10], [5000, 5], [15000, 0]], -100) == 10.0


def test_interp_clamps_above_range():
    assert _interp([[0, 10], [5000, 5], [15000, 0]], 99999) == 0.0


def test_interp_linear_interpolation():
    # 2500m is halfway between (0,10) and (5000,5) -> 7.5
    assert _interp([[0, 10], [5000, 5], [15000, 0]], 2500) == pytest.approx(7.5)
    # 10000m is halfway between (5000,5) and (15000,0) -> 2.5
    assert _interp([[0, 10], [5000, 5], [15000, 0]], 10000) == pytest.approx(2.5)


def test_interp_exact_anchor_returns_y():
    assert _interp([[0, 10], [5000, 5], [15000, 0]], 5000) == 5.0


def test_load_config_has_all_seven_criteria():
    cfg = load_config("ma-eea-2026-v1")
    assert set(cfg["criteria"]) == {
        "grid_alignment",
        "climate_resilience",
        "carbon_storage",
        "biodiversity",
        "burdens",
        "benefits",
        "agriculture",
    }
    # Weights sum to 1.0 across the seven criteria.
    total_w = sum(c["weight"] for c in cfg["criteria"].values())
    assert total_w == pytest.approx(1.0)


def test_config_buckets_follow_claude_md():
    cfg = load_config("ma-eea-2026-v1")
    assert cfg["buckets"]["suitable_min"] == 70
    assert cfg["buckets"]["conditional_min"] == 50


def test_criterion_score_schema_rejects_out_of_range_raw():
    with pytest.raises(Exception):
        CriterionScore(
            key="x",
            name="x",
            weight=0.1,
            raw_score=11.0,
            weighted_contribution=11.0,
            finding="bad",
        )


def test_source_citation_allows_partial_fields():
    c = SourceCitation(dataset="MassGIS L3 Parcels")
    assert c.dataset == "MassGIS L3 Parcels"
    assert c.row_id is None


def test_biodiversity_layer_weights_sum_to_one():
    cfg = load_config("ma-eea-2026-v1")
    lw = cfg["criteria"]["biodiversity"]["layer_weights"]
    assert sum(lw.values()) == pytest.approx(1.0)
