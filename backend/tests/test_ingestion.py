"""Unit tests for every ingestion script's feature → row transform.

These tests exercise the pure transform functions against small GeoJSON
fixtures. They do not hit the network or the database, so they run fast
and deterministically in CI.
"""

from __future__ import annotations

import json
from pathlib import Path

from ingest import biomap, fema_flood, l3_parcels, nhesp, wetlands
from ingest.esmp_projects import (
    classify_confidence,
    normalize_place_query,
    normalize_siting_status,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


# ---------------------------------------------------------------------------
# L3 parcels
# ---------------------------------------------------------------------------
def test_l3_parcels_transform_skips_missing_loc_id_and_geom():
    feats = _load("l3_parcels_mini.json")["features"]
    rows = [l3_parcels.feature_to_row(f, "Acton") for f in feats]
    good = [r for r in rows if r is not None]
    assert len(good) == 2
    assert good[0]["loc_id"] == "A1"
    assert good[0]["town_name"] == "Acton"
    assert good[0]["site_addr"] == "1 MAIN ST"
    # Geometry is forwarded as a JSON string for ST_GeomFromGeoJSON.
    assert json.loads(good[0]["geom"])["type"] == "Polygon"


# ---------------------------------------------------------------------------
# BioMap (core + cnl share a helper)
# ---------------------------------------------------------------------------
def test_biomap_core_transform_labels_layer_and_stores_attrs():
    feats = _load("biomap_core_mini.json")["features"]
    rows = [biomap.feature_to_row(f, "Forest Core", "core") for f in feats]
    good = [r for r in rows if r is not None]
    assert len(good) == 2
    assert all(r["core_type"] == "Forest Core" for r in good)
    attrs = json.loads(good[0]["attrs"])
    assert attrs["COMPNAME"] == "Test Community A"


def test_biomap_cnl_transform_uses_cnl_type_key():
    feats = _load("biomap_core_mini.json")["features"]  # same shape
    rows = [biomap.feature_to_row(f, "Landscape Blocks", "cnl") for f in feats if f["geometry"]]
    assert all("cnl_type" in r for r in rows)
    assert all("core_type" not in r for r in rows)


# ---------------------------------------------------------------------------
# NHESP
# ---------------------------------------------------------------------------
def test_nhesp_priority_transform():
    feats = _load("nhesp_priority_mini.json")["features"]
    rows = [nhesp.priority_row(f) for f in feats]
    good = [r for r in rows if r]
    assert len(good) == 2
    assert good[0]["priority_id"] == "PH-1"
    assert good[0]["source_version"] == "2024-08-01"


def test_nhesp_estimated_transform_falls_back_to_objectid():
    feats = _load("nhesp_estimated_mini.json")["features"]
    rows = [nhesp.estimated_row(f) for f in feats]
    assert rows[0]["estimated_id"] == "EH-1"
    assert rows[1]["source_version"] == "NHESP"  # no HAB_DATE in fixture


# ---------------------------------------------------------------------------
# FEMA flood
# ---------------------------------------------------------------------------
def test_fema_flood_transform():
    feats = _load("fema_flood_mini.json")["features"]
    rows = [fema_flood.feature_to_row(f) for f in feats]
    good = [r for r in rows if r]
    assert len(good) == 2
    assert good[0]["fld_zone"] == "AE"
    assert good[0]["static_bfe"] == 9.5
    assert good[0]["sfha_tf"] == "T"


# ---------------------------------------------------------------------------
# DEP wetlands
# ---------------------------------------------------------------------------
def test_wetlands_transform_prefers_desc_over_code():
    feats = _load("wetlands_mini.json")["features"]
    rows = [wetlands.feature_to_row(f) for f in feats]
    good = [r for r in rows if r]
    assert len(good) == 2
    assert good[0]["iw_type"] == "Shallow Marsh Meadow"
    assert good[0]["iw_class"] == "SMM"


# ---------------------------------------------------------------------------
# ESMP — query normalization + status vocabulary + confidence classifier
# ---------------------------------------------------------------------------
def test_normalize_place_query_parenthetical_neighborhood():
    q, has_n = normalize_place_query("Boston (East Boston)")
    assert q == "East Boston, Boston, MA"
    assert has_n is True


def test_normalize_place_query_expands_sq_abbreviation():
    q, has_n = normalize_place_query("Cambridge (Kendall Sq)")
    assert q == "Kendall Square, Cambridge, MA"
    assert has_n is True


def test_normalize_place_query_parenthetical_with_slash_takes_first_neighborhood():
    q, has_n = normalize_place_query("Boston (Hyde Park / Dorchester)")
    assert q == "Hyde Park, Boston, MA"
    assert has_n is True


def test_normalize_place_query_slash_without_parenthetical_takes_first_town():
    q, has_n = normalize_place_query("Marion / Fairhaven / Rochester")
    assert q == "Marion, MA"
    assert has_n is False


def test_normalize_place_query_plain_town():
    q, has_n = normalize_place_query("Acton")
    assert q == "Acton, MA"
    assert has_n is False


def test_normalize_place_query_directional_parenthetical():
    q, has_n = normalize_place_query("Cambridge (North)")
    assert q == "North Cambridge, MA"
    assert has_n is True


def test_normalize_siting_status_rules():
    assert normalize_siting_status("In construction (delayed from 2020 ISD)") == "under_construction"
    assert normalize_siting_status("EFSB Tentative Decision (late 2022)") == "in_permitting"
    assert normalize_siting_status("Approved / In Progress") == "under_construction"
    assert normalize_siting_status("Internally Approved") == "approved"
    assert normalize_siting_status("Planning Phase") == "planned"
    assert normalize_siting_status("Proposed CIP") == "planned"
    assert normalize_siting_status("Interim Operational Solution") == "in_service"


def test_classify_confidence_pending_siting_wins_over_places():
    geo = {"status": "OK", "types": ["sublocality"]}
    assert classify_confidence("New Worthington Substation", False, geo) == "pending_siting"


def test_classify_confidence_exact_when_neighborhood_and_sublocality_match():
    geo = {"status": "OK", "types": ["sublocality", "political"]}
    assert classify_confidence("New East Eagle Substation #131", True, geo) == "exact"


def test_classify_confidence_exact_even_without_parenthetical_when_places_returns_neighborhood():
    # East Freetown is typed as 'neighborhood' by Places though the xlsx
    # source has no parenthetical — that's still a genuine sub-town match.
    geo = {"status": "OK", "types": ["neighborhood", "political"]}
    assert (
        classify_confidence("East Freetown Group CIP (replaces New Bedford)", False, geo)
        == "exact"
    )


def test_classify_confidence_approximate_without_neighborhood():
    geo = {"status": "OK", "types": ["locality", "political"]}
    assert classify_confidence("Somerville Substation #402 Expansion", False, geo) == "approximate"
