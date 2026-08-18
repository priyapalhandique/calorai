"""Audit agent tests — end-to-end deterministic pipeline in mock mode."""

import pytest

from calorai.agent import AuditAgent, AuditError, AuditRequest


def _request(**kwargs):
    defaults = dict(district="phoenix", date="2026-08-18", hour=14, data_source="mock")
    defaults.update(kwargs)
    return AuditRequest(**defaults)


def test_full_audit_mock_produces_all_sections():
    report = AuditAgent(_request()).run(narrate=False)
    assert report["district"] == "Phoenix, AZ"
    assert report["date"] == "2026-08-18"
    assert report["source"] == "mock"

    snapshot = report["snapshot"]
    assert snapshot["n_cells"] == 81
    assert 20.0 < snapshot["min_c"] <= snapshot["mean_c"] <= snapshot["max_c"] < 55.0
    assert "hottest_tile" in snapshot

    attribution = report["attribution"]
    assert attribution["solar_share"] > 50.0  # solar dominates daytime Phoenix
    total = (
        attribution["solar_share"]
        + attribution["longwave_share"]
        + attribution["convection_share"]
    )
    assert total == pytest.approx(100.0, abs=0.2)

    inertia = report["inertia"]
    assert 0.0 < inertia["overnight_retention"] < 1.0
    assert inertia["thermal_effusivity"] > 0.0

    exposure = report["exposure"]
    assert exposure["wbgt_c"] > 0.0
    assert exposure["overall_risk"] in ("low", "medium", "high")
    assert exposure["exceedance_hours"] >= 0.0  # key the narrator needs

    assert len(report["interventions"]) >= 2
    deltas = [iv["delta_t_c"] for iv in report["interventions"]]
    assert deltas == sorted(deltas, reverse=True)  # best first
    assert all(iv["delta_t_c"] > 0.0 for iv in report["interventions"])
    assert all("basis" in iv for iv in report["interventions"])

    assert "Stefan-Boltzmann" in report["provenance"]
    assert report["one_liner"]


def test_narrative_is_non_empty_markdown():
    report = AuditAgent(_request()).run(narrate=True)
    narrative = report["narrative"]
    assert narrative.startswith("#")
    assert "Phoenix" in narrative
    assert "Intervention" in narrative or "intervention" in narrative
    for iv in report["interventions"]:
        assert f"{iv['delta_t_c']:.1f}" in narrative


def test_cooler_district_flags_lower_risk():
    hot = AuditAgent(_request(district="phoenix")).run(narrate=False)
    mild = AuditAgent(_request(district="san-jose")).run(narrate=False)
    assert hot["snapshot"]["max_c"] > mild["snapshot"]["max_c"]
    assert hot["exposure"]["wbgt_c"] > mild["exposure"]["wbgt_c"]


def test_audit_is_deterministic_across_runs():
    a = AuditAgent(_request()).run(narrate=False)
    b = AuditAgent(_request()).run(narrate=False)
    assert a == b


def test_bad_hour_and_date_rejected():
    with pytest.raises(AuditError):
        AuditAgent(_request(hour=24))
    with pytest.raises(AuditError):
        AuditAgent(_request(date="2020-01-01"))


def test_exceedance_optional():
    report = AuditAgent(_request(with_exceedance=False)).run(narrate=False)
    assert report["exposure"]["exceedance_hours"] == 0.0


def test_phoenix_heat_stress_is_high():
    report = AuditAgent(_request(district="phoenix")).run(narrate=False)
    level = report["exposure"]["level"]
    assert level in ("high", "very_high", "extreme", "moderate")