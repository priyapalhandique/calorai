"""D7 — agentic core: tools registry, planner, responder, sentinel."""

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.pop("GITHUB_MODELS_TOKEN", None)
os.environ.pop("GITHUB_TOKEN", None)

from calorai.agent import AuditAgent, AuditRequest
from calorai.planner import deterministic_plan, plan_and_run
from calorai.responder import heat_response_plan, misting_plan
from calorai.sentinel import evaluate_alerts
from calorai.tools import AgentContext, execute_tool, list_tools


@pytest.fixture
def ctx() -> AgentContext:
    return AgentContext(district="phoenix", date="2026-08-18", hour=14, threshold_c=30.0)


# ---------------------------------------------------------------- registry


def test_registry_has_required_tools():
    names = [t["name"] for t in list_tools()]
    for required in (
        "audit", "forecast", "anomaly", "risk", "respond_mist", "equity",
        "productivity", "economy", "thermal_wind", "downburst", "aviation",
        "export", "usage",
    ):
        assert required in names


def test_registry_entries_wellformed():
    for t in list_tools():
        assert t["name"] and t["description"] and t["keywords"]


def test_execute_unknown_tool_returns_error():
    tr = execute_tool("nope", {}, AgentContext())
    assert not tr.ok
    assert "unknown" in tr.error


# ---------------------------------------------------------------- tools


def test_audit_tool(ctx):
    tr = execute_tool("audit", {"district": "phoenix"}, ctx)
    assert tr.ok
    assert tr.result["district"]
    assert tr.result["snapshot"]["max_c"] > tr.result["snapshot"]["min_c"]
    assert "response" in tr.result and "alerts" in tr.result


def test_forecast_tool_district_24h(ctx):
    tr = execute_tool("forecast", {"district": "phoenix"}, ctx)
    assert tr.ok
    assert tr.result["mode"] == "district_24h"
    assert 0 <= tr.result["peak_hour"] <= 23
    assert tr.result["peak_skin_c"] > 20.0


def test_forecast_tool_explicit_features(ctx):
    features = {
        "irradiance_w_m2": 900.0, "albedo": 0.12, "emissivity": 0.93,
        "convective_coefficient": 12.0, "air_temperature_c": 38.0,
        "radiative_environment_c": 33.0, "storage_flux_w_m2": 100.0,
        "latent_flux_w_m2": 30.0,
    }
    tr = execute_tool("forecast", features, ctx)
    assert tr.ok
    assert tr.result["mode"] == "explicit"
    assert 25.0 < tr.result["predicted_skin_c"] < 80.0


def test_risk_tool(ctx):
    tr = execute_tool("risk", {"district": "phoenix"}, ctx)
    assert tr.ok
    assert tr.result["exposure"]["wbgt_c"] > 20.0
    assert tr.result["downburst"]["peak_risk"] in ("low", "medium", "high")


def test_respond_mist_tool_active_on_dry_hot(ctx):
    tr = execute_tool("respond_mist", {"district": "phoenix"}, ctx)
    assert tr.ok
    mist = tr.result["misting"]
    assert mist["level"] in ("active", "guard", "limited")
    assert mist["placement"]
    assert tr.result["heat_response"]["actions"]


def test_equity_tool_with_leaderboard(ctx):
    tr = execute_tool("equity", {"district": "phoenix", "benchmark": True}, ctx)
    assert tr.ok
    assert tr.result["n_districts"] >= 2
    assert tr.result["leaderboard"][0]["district"]


def test_productivity_economy_thermal_wind_downburst(ctx):
    for name, key in (("productivity", "moderate"), ("economy", "total_usd_per_year"),
                      ("thermal_wind", "inflow_direction_deg"), ("downburst", "peak_risk")):
        tr = execute_tool(name, {"district": "phoenix"}, ctx)
        assert tr.ok, name
        assert key in tr.result, name


def test_aviation_tool(ctx):
    tr = execute_tool("aviation", {"district": "phoenix"}, ctx)
    assert tr.ok
    assert tr.result["density_altitude_m"] > 0.0
    assert tr.result["takeoff_distance_factor"] > 1.0
    assert tr.result["surface_risk"]


def test_usage_tool_mock(ctx):
    tr = execute_tool("usage", {"source": "mock"}, ctx)
    assert tr.ok
    assert tr.result["mode"] == "mock"


def test_export_tool(ctx):
    tr = execute_tool("export", {"district": "phoenix"}, ctx)
    assert tr.ok
    assert tr.result["bytes"] > 1000
    assert tr.result["ready"]


# ---------------------------------------------------------------- planner


def test_deterministic_plan_chain():
    steps, mode = deterministic_plan("plan tomorrow for Maryvale", AgentContext())
    assert mode == "chain:plan"
    names = [s["tool"] for s in steps]
    assert names == ["audit", "forecast", "risk", "respond_mist"]
    assert steps[0]["args"]["district"] == "maryvale"


def test_deterministic_plan_single_tool():
    steps, mode = deterministic_plan("how much does heat cost in Las Vegas", AgentContext())
    assert mode == "tool:economy"
    assert steps[0]["tool"] == "economy"
    assert steps[0]["args"]["district"] == "vegas-strip"


def test_deterministic_plan_aviation():
    steps, mode = deterministic_plan("runway takeoff analysis for Phoenix", AgentContext())
    assert mode == "tool:aviation"
    assert steps[0]["tool"] == "aviation"


def test_deterministic_plan_fallback():
    steps, mode = deterministic_plan("zzz unknown gibberish", AgentContext())
    assert mode == "fallback"
    assert steps[0]["tool"] == "audit"


def test_plan_and_run_returns_answer_and_trace(ctx):
    out = plan_and_run("audit phoenix", ctx)
    assert out["answer"]
    assert "Mode:" in out["answer"]
    assert out["trace"]
    assert out["trace"][0]["tool"] == "audit"
    assert out["trace"][0]["ok"]


def test_plan_and_run_chain_uses_memoized_audit(ctx):
    out = plan_and_run("plan tomorrow for East Harlem", ctx)
    names = [t["tool"] for t in out["trace"]]
    assert names == ["audit", "forecast", "risk", "respond_mist"]
    assert all(t["ok"] for t in out["trace"])
    assert out["refinement"] in ("llm-failed", "no-token", "ok")


def test_plan_and_run_offline_never_calls_network(ctx):
    out = plan_and_run("inspect San Jose anomalies", ctx)
    assert out["trace"][0]["tool"] == "audit"
    assert out["answer"]


# ---------------------------------------------------------------- responder


def test_misting_humid_air_limited():
    plan = misting_plan(
        wbgt_c=32.0, humidity_pct=85.0, wind_speed_m_s=1.0,
        air_temp_c=35.0, inflow_direction_deg=90.0,
    )
    assert plan["level"] == "limited"


def test_misting_high_wind_guard():
    plan = misting_plan(
        wbgt_c=32.0, humidity_pct=20.0, wind_speed_m_s=6.0,
        air_temp_c=35.0, inflow_direction_deg=90.0,
    )
    assert plan["level"] == "guard"


def test_misting_cool_air_none():
    plan = misting_plan(
        wbgt_c=22.0, humidity_pct=20.0, wind_speed_m_s=1.0,
        air_temp_c=24.0, inflow_direction_deg=None,
    )
    assert plan["level"] == "none"


def test_heat_response_extreme():
    plan = heat_response_plan(35.0)
    assert plan["band"] == "extreme"
    assert "Stop" in plan["actions"][0]["action"]


def test_heat_response_low():
    plan = heat_response_plan(21.0)
    assert plan["band"] == "low"


# ---------------------------------------------------------------- sentinel


def test_sentinel_fires_on_hot_report(ctx):
    report = ctx.report(district="phoenix")
    alerts = evaluate_alerts(report)
    assert alerts["present"]
    assert alerts["n_alerts"] >= 1
    assert alerts["webhook_payload"]["service"] == "calorai-sentinel"


def test_sentinel_quiet_on_cool_report(ctx):
    report = ctx.report(district="phoenix", hour=5)
    if report["exposure"]["wbgt_c"] >= 31.0:
        pytest.skip("hour 5 mock data not cool enough")
    alerts = evaluate_alerts(report)
    fired = {a["id"] for a in alerts["alerts"]}
    assert not fired & {"R1_tile_max", "R2_wbgt", "R5_downburst"}


def test_sentinel_rule_units():
    from calorai.sentinel.alerts import ALERT_RULES
    assert {r["id"] for r in ALERT_RULES} == {
        "R1_tile_max", "R2_wbgt", "R3_exceedance", "R4_retention",
        "R5_downburst", "R6_anomaly", "R7_equity",
    }


# ---------------------------------------------------------------- agent wiring


def test_agent_report_has_response_and_alerts():
    agent = AuditAgent(AuditRequest(district="phoenix", date="2026-08-18", hour=14))
    report = agent.run(narrate=False)
    assert report["response"]["misting"]["level"]
    assert report["response"]["heat_response"]["band"]
    assert "alerts" in report
    assert report["alerts"]["present"]


def test_audit_blocks_consistent_with_tools(ctx):
    report = ctx.report(district="phoenix")
    tr = execute_tool("anomaly", {"district": "phoenix"}, ctx)
    assert tr.result["n_tiles"] == report["analysis"]["anomaly"]["n_tiles"]