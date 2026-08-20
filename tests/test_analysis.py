"""M4 analyst + circulation/downburst tests — equity, productivity,
economy, thermal-wind proxy and downburst diagnostic."""

import pytest

from calorai.agent import AuditAgent, AuditRequest
from calorai.analyst import (
    annualized_loss,
    cross_district_leaderboard,
    district_cost_of_heat,
    gini,
    heat_burden,
    work_capacity_loss_pct,
)
from calorai.physics.downburst import downburst_risk_series, outflow_watch_text
from calorai.physics.thermal_wind import (
    pressure_perturbation_pa,
    temperature_gradient_deg,
    urban_circulation,
)

# ---------------------------------------------------------------- equity


def test_gini_uniform_is_zero():
    assert gini([30.0] * 50) == 0.0


def test_gini_extreme_split_approaches_half():
    g = gini([0.0] * 10 + [10.0] * 10)
    assert 0.4 < g < 0.55


def test_gini_single_and_empty():
    assert gini([5.0]) == 0.0
    assert gini([]) == 0.0


def test_heat_burden_profile():
    tiles = [{"lat": 0.0, "lon": 0.0, "value": 42.0}] * 40 + [
        {"lat": 0.0, "lon": 0.1, "value": 55.0}
    ] * 10
    burden = heat_burden(tiles, threshold_c=50.0)
    assert burden["present"] is True
    assert burden["n_tiles"] == 50
    assert burden["share_above_threshold_pct"] == 20.0
    assert burden["quintile_gap_c"] > 0.0
    assert 0.0 < burden["gini"] < 1.0


# ---------------------------------------------------------- productivity


def test_capacity_loss_tiny_below_threshold():
    # Logistic curves asymptote to zero; below the onset the loss must
    # be negligible (<1%) even if not exactly 0.
    assert work_capacity_loss_pct(25.0, "light") < 1.0
    assert work_capacity_loss_pct(22.0, "heavy") == 0.0


def test_capacity_loss_bounds_and_ordering():
    heavy = work_capacity_loss_pct(31.0, "heavy")
    moderate = work_capacity_loss_pct(31.0, "moderate")
    light = work_capacity_loss_pct(31.0, "light")
    assert 0.0 <= light < moderate < heavy <= 40.0


def test_capacity_loss_monotonic():
    vals = [work_capacity_loss_pct(w, "moderate") for w in range(24, 35)]
    assert vals == sorted(vals)


def test_annualized_loss_reports_assumptions():
    loss = annualized_loss(wbgt_c=31.0)
    assert loss["usd_per_year"] > 0.0
    assert "curve" in loss["assumptions"]


# --------------------------------------------------------------- economy


def test_cost_of_heat_is_additive():
    roi = {"annual_savings_usd": 12_000.0, "annual_energy_avoided_kwh": 40_000.0}
    cost = district_cost_of_heat(roi, wbgt_c=30.0)
    assert cost["total_usd_per_year"] == pytest.approx(
        cost["cooling_usd_per_year"] + cost["productivity_usd_per_year"]
    )
    assert cost["cooling_usd_per_year"] == 12_000.0
    assert "assumptions" in cost


# ---------------------------------------------------------- thermal wind


def test_gradient_plane_fit_recovers_slopes():
    tiles = [
        {"lat": 10.0 + dy, "lon": 10.0 + dx, "value": 40.0 + 2.0 * dx + 3.0 * dy}
        for dx, dy in [(0.0, 0.0), (1.0, 0.0), (0.0, 1.0), (1.0, 1.0), (0.5, 0.25)]
    ]
    grad = temperature_gradient_deg(tiles)
    assert grad["b"] == pytest.approx(2.0, abs=1e-6)
    assert grad["c"] == pytest.approx(3.0, abs=1e-6)
    assert grad["k_per_deg"] == pytest.approx(3.60555, abs=1e-3)


def test_circulation_points_toward_hot_core():
    # Hot core in the east: tiles warm up with increasing lon.
    tiles = [
        {"lat": 33.0, "lon": -112.0 + 0.002 * i, "value": 44.0 + 0.8 * i}
        for i in range(20)
    ]
    circ = urban_circulation(tiles, mean_temp_c=50.0)
    assert circ["present"] is True
    # East is hotter (bearing 90 deg); inflow should head east.
    assert 45.0 <= circ["inflow_direction_deg"] <= 135.0
    assert circ["pressure_deficit_hpa"] > 0.0
    assert circ["inflow_speed_scale_m_s"] > 0.0
    # Thermal wind runs perpendicular to the temperature gradient.
    diff = abs(circ["thermal_wind_direction_deg"] - circ["inflow_direction_deg"])
    assert diff == pytest.approx(90.0, abs=10.0)


def test_pressure_deficit_scales_with_excess():
    cold = [{"lat": 0.0, "lon": 0.0, "value": 40.0}] * 9 + [
        {"lat": 0.0, "lon": 1.0, "value": 42.0}
    ]
    hot = [{"lat": 0.0, "lon": 0.0, "value": 40.0}] * 9 + [
        {"lat": 0.0, "lon": 1.0, "value": 52.0}
    ]
    assert pressure_perturbation_pa(hot, 40.0) > pressure_perturbation_pa(cold, 40.0)


# ------------------------------------------------------------- downburst


def _env(apparent, wet_bulb, precip):
    return {
        "hour": list(range(24)),
        "apparent_c": apparent,
        "wet_bulb_c": wet_bulb,
        "precipitation_mm": precip,
    }


def test_downburst_high_when_rain_through_dry_air():
    # Dry desert air (apparent 40, wet-bulb 22 -> D=18) + rain = high.
    apparent = [40.0] * 24
    wet = [22.0] * 24
    precip = [0.0] * 15 + [4.0, 8.0, 5.0, 1.0] + [0.0] * 5
    db = downburst_risk_series(_env(apparent, wet, precip))
    assert db["present"] is True
    assert db["peak_risk"] == "high"
    assert db["hours_high"] >= 1
    assert db["peak_depression_k"] == pytest.approx(18.0, abs=0.01)


def test_downburst_low_when_rain_through_humid_air():
    apparent = [35.0] * 24
    wet = [32.0] * 24  # D = 3: no evaporation potential
    precip = [0.0] * 15 + [4.0] * 4 + [0.0] * 5
    db = downburst_risk_series(_env(apparent, wet, precip))
    assert db["peak_risk"] == "low"
    assert db["hours_high"] == 0


def test_downburst_low_when_dry_but_no_rain():
    apparent = [40.0] * 24
    wet = [22.0] * 24
    precip = [0.0] * 24
    db = downburst_risk_series(_env(apparent, wet, precip))
    assert db["peak_risk"] == "low"
    assert "no rain" in db["advisory"].lower() or db["peak_risk"] == "low"


def test_downburst_empty_env_returns_present_false():
    assert downburst_risk_series({})["present"] is False


def test_outflow_watch_text_maps_all_bands():
    assert outflow_watch_text("low")
    assert "OUTFLOW WATCH" in outflow_watch_text("high")


# ------------------------------------------------------------- agent block


def _request(**kwargs):
    defaults = dict(district="phoenix", date="2026-08-18", hour=14, data_source="mock")
    defaults.update(kwargs)
    return AuditRequest(**defaults)


def test_agent_report_has_m4_blocks():
    report = AuditAgent(_request()).run(narrate=False)
    analysis = report["analysis"]
    assert analysis["equity"]["present"] is True
    assert analysis["equity"]["gini"] >= 0.0
    assert analysis["productivity"]["wbgt_c"] > 0.0
    assert analysis["economy"]["total_usd_per_year"] > 0.0
    assert report["thermal_wind"]["present"] is True
    assert report["thermal_wind"]["pressure_deficit_hpa"] > 0.0
    assert report["downburst"]["present"] is True
    assert report["downburst"]["peak_risk"] in ("low", "medium", "high")
    assert "thermal-wind proxy" in report["provenance"]


def test_agent_mock_humid_rain_stays_low():
    report = AuditAgent(
        AuditRequest(district="east-harlem", date="2026-08-18", hour=16, data_source="mock")
    ).run(narrate=False)
    db = report["downburst"]
    assert db["peak_risk"] == "low"
    assert db["hours_high"] == 0


def test_leaderboard_ranks_all_districts():
    board = cross_district_leaderboard(
        ["phoenix", "san-jose", "manhattan", "chicago", "austin",
         "maryvale", "vegas-strip", "east-harlem"],
        "2026-08-18",
    )
    assert len(board) == 8
    wbgts = [r["wbgt_c"] for r in board]
    assert wbgts == sorted(wbgts, reverse=True)
    assert all(r["key"] for r in board)
    assert all(r["gini"] is not None for r in board)