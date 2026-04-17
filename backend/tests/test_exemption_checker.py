"""Unit tests for services.exemption_checker — all 6 rules from 225 CMR 29.07(1).

Pure function, no DB access. Just fabricated input dicts through the
function + assertion on the return shape.
"""

from __future__ import annotations

from app.services.exemption_checker import check_exemption


class TestFootprintRule:
    """225 CMR 29.07(1)(1) — site footprint < 1 acre."""

    def test_footprint_under_one_acre_is_exempt(self):
        r = check_exemption("solar_ground_mount", site_footprint_acres=0.8)
        assert r.is_exempt is True
        assert "< 1 acre" in r.reason

    def test_footprint_exactly_one_acre_is_not_exempt(self):
        r = check_exemption(
            "solar_ground_mount",
            site_footprint_acres=1.0,
            nameplate_capacity_kw=500,
        )
        assert r.is_exempt is False

    def test_large_footprint_is_not_exempt(self):
        r = check_exemption(
            "solar_ground_mount",
            site_footprint_acres=5.0,
            nameplate_capacity_kw=1000,
        )
        assert r.is_exempt is False


class TestSolarCapacityRule:
    """225 CMR 29.07(1)(2) — solar ≤ 25 kW AC."""

    def test_residential_solar_is_exempt(self):
        r = check_exemption(
            "solar_rooftop",
            nameplate_capacity_kw=10.0,
            site_footprint_acres=0.01,
        )
        assert r.is_exempt is True
        # Behind-the-meter rule does not fire since is_behind_meter=False;
        # should hit solar ≤ 25 kW AC (rule 2) first per precedence.
        assert "25 kW" in r.reason or "< 1 acre" in r.reason

    def test_solar_exactly_25kw_is_exempt(self):
        r = check_exemption(
            "solar_rooftop",
            nameplate_capacity_kw=25.0,
            site_footprint_acres=2.0,
        )
        assert r.is_exempt is True
        assert "25 kW" in r.reason

    def test_large_solar_is_not_exempt(self):
        r = check_exemption(
            "solar_ground_mount",
            nameplate_capacity_kw=1000.0,
            site_footprint_acres=5.0,
        )
        assert r.is_exempt is False

    def test_capacity_rule_does_not_apply_to_bess(self):
        # 10 kWh BESS is not exempt under the solar kW rule.
        r = check_exemption(
            "bess_standalone",
            nameplate_capacity_kw=10.0,
            site_footprint_acres=5.0,
        )
        assert r.is_exempt is False


class TestBehindMeterRule:
    """225 CMR 29.07(1)(3) and (4) — BTM (any size) and accessory BTM."""

    def test_behind_meter_is_exempt_regardless_of_size(self):
        r = check_exemption(
            "solar_ground_mount",
            nameplate_capacity_kw=500.0,
            site_footprint_acres=3.0,
            is_behind_meter=True,
        )
        assert r.is_exempt is True
        assert "behind-the-meter" in r.reason

    def test_accessory_behind_meter_surfaces_as_accessory(self):
        r = check_exemption(
            "solar_rooftop",
            is_behind_meter=True,
            is_accessory_use=True,
        )
        assert r.is_exempt is True
        assert "accessory-use" in r.reason


class TestTandDRules:
    """225 CMR 29.07(1)(5) and (6) — T&D in public ROW or ≤ 20 kV."""

    def test_td_in_public_row_is_exempt(self):
        r = check_exemption(
            "transmission",
            in_existing_public_row=True,
            site_footprint_acres=10.0,
        )
        assert r.is_exempt is True
        assert "right of way" in r.reason

    def test_low_voltage_td_is_exempt(self):
        r = check_exemption(
            "substation",
            td_design_rating_kv=13.8,
            site_footprint_acres=2.0,
        )
        assert r.is_exempt is True
        assert "20 kV" in r.reason

    def test_td_at_exactly_20kv_is_exempt(self):
        r = check_exemption(
            "transmission",
            td_design_rating_kv=20.0,
            site_footprint_acres=5.0,
        )
        assert r.is_exempt is True

    def test_high_voltage_td_is_not_exempt(self):
        r = check_exemption(
            "transmission",
            td_design_rating_kv=115.0,
            site_footprint_acres=5.0,
        )
        assert r.is_exempt is False


class TestInsufficientData:
    """When the caller doesn't supply what's needed, return None — don't guess."""

    def test_solar_without_capacity_or_footprint_is_insufficient(self):
        r = check_exemption("solar_ground_mount")
        assert r.is_exempt is None
        assert r.reason == "insufficient_data"
        assert "nameplate_capacity_kw" in r.missing_fields
        assert "site_footprint_acres" in r.missing_fields

    def test_td_without_rating_is_insufficient(self):
        r = check_exemption("transmission")
        assert r.is_exempt is None
        assert "td_design_rating_kv" in r.missing_fields

    def test_bess_without_footprint_is_insufficient(self):
        r = check_exemption("bess_standalone")
        assert r.is_exempt is None
        assert "site_footprint_acres" in r.missing_fields


class TestPrecedence:
    """Behind-the-meter short-circuits every other rule."""

    def test_btm_takes_precedence_over_non_solar_type(self):
        r = check_exemption(
            "bess_standalone",
            is_behind_meter=True,
        )
        assert r.is_exempt is True
        assert "behind-the-meter" in r.reason
