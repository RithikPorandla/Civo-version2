"""Tests for services.doer_comparison with synthetic town bylaws.

Fixtures mimic the shape of project_type_bylaws JSONB (see scripts/seed_bylaws.py)
and the DOER model JSON (see data/processed/doer/solar_model_bylaw.json).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.services.doer_comparison import compare_solar_to_doer_model

DOER_JSON = (
    Path(__file__).resolve().parents[2]
    / "data"
    / "processed"
    / "doer"
    / "solar_model_bylaw.json"
)


@pytest.fixture(scope="module")
def doer_model() -> dict:
    return json.loads(DOER_JSON.read_text())["data"]


def _clean_town() -> dict:
    """Town fully aligned with the DOER model — by-right at all sizes.

    Deliberately permissive to verify the engine returns zero deviations.
    """
    return {
        "solar_ground_mount": {
            "approval_authority": "Planning Board",
            "process": "by_right",
            "setbacks_ft": {"front": 20, "side": 20, "rear": 25},
            "acreage_cap": None,
            "overlay_districts": [],
        }
    }


def _uniform_treatment_town() -> dict:
    """Town applies special-permit uniformly — fires Tracer Lane."""
    return {
        "solar_ground_mount": {
            "approval_authority": "Planning Board",
            "process": "special_permit",
            "setbacks_ft": {"front": 20, "side": 20, "rear": 25},
            "acreage_cap": None,
            "overlay_districts": [],
        }
    }


def _acreage_cap_town() -> dict:
    return {
        "solar_ground_mount": {
            "approval_authority": "Planning Board",
            "process": "site_plan_review",
            "setbacks_ft": {"front": 20, "side": 20, "rear": 25},
            "acreage_cap": 5,
            "deforestation_cap_acres": 1,  # Acton-style
            "overlay_districts": [],
        }
    }


def _overlay_town() -> dict:
    return {
        "solar_ground_mount": {
            "approval_authority": "Planning Board",
            "process": "site_plan_review",
            "setbacks_ft": {"front": 50, "side": 50, "rear": 50},
            "acreage_cap": None,
            "overlay_districts": ["Solar Overlay District"],
        }
    }


class TestCleanTown:
    def test_no_deviations_when_aligned(self, doer_model):
        r = compare_solar_to_doer_model(_clean_town(), doer_model)
        assert r.comparison_available is True
        assert r.deviations == []
        assert r.dover_amendment_risk is False


class TestUniformTreatment:
    def test_fires_uniform_treatment_flag(self, doer_model):
        r = compare_solar_to_doer_model(_uniform_treatment_town(), doer_model)
        assert r.comparison_available is True
        cats = [d.category for d in r.deviations]
        assert "uniform_treatment" in cats
        ut = next(d for d in r.deviations if d.category == "uniform_treatment")
        assert ut.severity == "major"
        assert ut.dover_risk is True

    def test_suppresses_per_bucket_process_severity_dupes(self, doer_model):
        r = compare_solar_to_doer_model(_uniform_treatment_town(), doer_model)
        assert not any(d.category == "process_severity" for d in r.deviations)


class TestAcreageCap:
    def test_fires_acreage_cap(self, doer_model):
        r = compare_solar_to_doer_model(_acreage_cap_town(), doer_model)
        cats = [d.category for d in r.deviations]
        assert "acreage_cap_restriction" in cats
        ac = next(d for d in r.deviations if d.category == "acreage_cap_restriction")
        assert ac.severity == "major"
        assert ac.dover_risk is True

    def test_also_fires_deforestation_cap_as_minor_informational(self, doer_model):
        r = compare_solar_to_doer_model(_acreage_cap_town(), doer_model)
        dc = [d for d in r.deviations if d.category == "deforestation_cap"]
        assert dc, "deforestation_cap should be surfaced"
        assert dc[0].severity == "minor"
        assert dc[0].dover_risk is False


class TestOverlayRestriction:
    def test_overlay_is_flagged(self, doer_model):
        r = compare_solar_to_doer_model(_overlay_town(), doer_model)
        cats = [d.category for d in r.deviations]
        assert "overlay_restriction" in cats
        ov = next(d for d in r.deviations if d.category == "overlay_restriction")
        assert ov.dover_risk is True

    def test_setback_delta_fires_on_50ft_vs_20ft(self, doer_model):
        r = compare_solar_to_doer_model(_overlay_town(), doer_model)
        sd = [d for d in r.deviations if d.category == "setback_delta"]
        # 50 ft town vs 20 ft DOER front = 2.5×, should flag major
        assert any(d.severity == "major" for d in sd)


class TestMissingData:
    def test_empty_bylaws_returns_unavailable(self, doer_model):
        r = compare_solar_to_doer_model({}, doer_model)
        assert r.comparison_available is False
        assert r.reason_unavailable

    def test_no_solar_entry_returns_unavailable(self, doer_model):
        r = compare_solar_to_doer_model({"bess_standalone": {}}, doer_model)
        assert r.comparison_available is False


class TestDeviationCountsAndVersionPin:
    def test_counts_match_deviations(self, doer_model):
        r = compare_solar_to_doer_model(_acreage_cap_town(), doer_model)
        total = (
            r.deviation_counts["minor"]
            + r.deviation_counts["moderate"]
            + r.deviation_counts["major"]
        )
        assert total == len(r.deviations)

    def test_doer_version_is_pinned(self, doer_model):
        r = compare_solar_to_doer_model(_clean_town(), doer_model)
        assert r.doer_version_compared == doer_model["version"]
