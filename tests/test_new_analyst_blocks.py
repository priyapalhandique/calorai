"""Focused tests for the OpenCode-added analyst blocks."""

import json

import pytest

from calorai.analyst import carbon, citizen, resilience, time_machine


def test_carbon_block_handles_missing_delta_and_calculates_outputs():
    assert carbon.carbon_block(None) == {"present": False, "reason": "no whatif delta"}

    result = carbon.carbon_block(-13.0, district="phoenix")

    assert result["present"] is True
    assert result["district"] == "phoenix"
    assert result["delta_t_c"] == -13.0
    assert result["kwh_per_year"] == 6500.0
    assert result["co2_tons_per_year"] == 2.6
    assert result["grid_mw_peak_shave"] == 32.5


def test_resilience_block_scores_components_and_prioritizes_actions():
    result = resilience.resilience_block(
        {
            "uhi": {"score": 80},
            "vulnerability": {"score": {"score": 90}},
            "lake_effect": {"lake_detected": False},
            "landcover": {"green_pct": 2},
            "schedule": {"rows": [{"work_pct": 35}, {"work_pct": 80}]},
        }
    )

    assert result["present"] is True
    assert result["score"] == 36
    assert result["band"] == "low"
    assert result["components"]["work"] == 65
    assert len(result["ranked_actions"]) == 5
    assert "Activate heat-response + misting schedule" in result["ranked_actions"]


def test_resilience_block_is_safe_for_empty_report():
    result = resilience.resilience_block({})

    assert result["present"] is True
    assert 0 <= result["score"] <= 100
    assert result["ranked_actions"]


def test_time_machine_assembles_four_slider_blocks(monkeypatch, tmp_path):
    class FakeAudit:
        def __init__(self, request):
            self.request = request

        def run(self, narrate=False):
            return {
                "diurnal": {"apparent_c": list(range(24))},
                "snapshot": {"max_c": 44.0},
                "whatif": {"delta_t_c": -8.5},
            }

    class FakeRequest:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    monkeypatch.setattr("calorai.agent.AuditAgent", FakeAudit)
    monkeypatch.setattr("calorai.agent.AuditRequest", FakeRequest)
    monkeypatch.setattr("calorai.ml.forecast.load_forecast", lambda: object())
    monkeypatch.setattr("calorai.ml.forecast.forecast_skin_temp", lambda features, model: 46.25)
    monkeypatch.chdir(tmp_path)

    result = time_machine.time_machine_block("phoenix", "2026-08-18")

    assert result["slider"] == ["past", "present", "future", "whatif"]
    assert result["present_block"]["apparent_series"] == list(range(8))
    assert result["present_block"]["max_c"] == 44.0
    assert result["future"]["peak_skin_c"] == 46.2
    assert result["whatif"]["albedo_0_5_delta_c"] == -8.5


def test_citizen_report_is_truncated_and_mesh_reads_json(monkeypatch, tmp_path):
    monkeypatch.setattr(citizen, "CITIZEN_DIR", tmp_path)

    report = citizen.report_heat(33.45, -112.07, "phoenix", "x" * 300)
    result = citizen.mesh()

    assert report["lat"] == pytest.approx(33.45)
    assert report["lon"] == pytest.approx(-112.07)
    assert len(report["note"]) == 200
    assert result["n_reports"] == 1
    assert result["reports"][0]["id"] == report["id"]
    assert json.loads((tmp_path / f"{report['id']}.json").read_text())["district"] == "phoenix"