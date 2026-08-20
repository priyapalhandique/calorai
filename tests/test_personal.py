"""D8 — personal intelligence layer: profile, personalization, follow-ups."""

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.pop("GITHUB_MODELS_TOKEN", None)
os.environ.pop("GITHUB_TOKEN", None)

from calorai.personal import UserProfile, c_to_f, format_temp
from calorai.planner import plan_and_run
from calorai.tools import AgentContext


def test_profile_defaults():
    p = UserProfile.from_dict(None)
    assert p.units == "c"
    assert p.intensity == "moderate"
    assert p.threshold_c is None
    assert p.home_district is None


def test_profile_parsing_fallbacks():
    p = UserProfile.from_dict(
        {
            "units": "kelvin",
            "intensity": "extreme",
            "threshold_c": "not-a-number",
            "home_district": "   ",
        }
    )
    assert p.units == "c"
    assert p.intensity == "moderate"
    assert p.threshold_c is None
    assert p.home_district is None


def test_profile_parsing_valid():
    p = UserProfile.from_dict(
        {"units": "f", "intensity": "heavy", "threshold_c": 28.5, "home_district": "maryvale"}
    )
    assert p.units == "f"
    assert p.intensity == "heavy"
    assert p.threshold_c == 28.5
    assert p.home_district == "maryvale"


def test_c_to_f():
    assert c_to_f(0.0) == pytest.approx(32.0)
    assert c_to_f(41.2) == pytest.approx(106.16, abs=0.01)


def test_format_temp_units():
    assert format_temp(41.2, "c") == "41.2 °C"
    assert format_temp(41.2, "f").startswith("106.2 °F")


def test_home_district_fallback():
    ctx = AgentContext(district="phoenix", date="2026-08-18", hour=14)
    profile = UserProfile.from_dict({"home_district": "maryvale"})
    out = plan_and_run("how hot is it today", ctx, profile=profile)
    assert out["mode"].startswith(("tool", "chain:", "fallback"))
    # the audit ran on the profile's home district
    trace_districts = [
        t["result"]["district"] for t in out["trace"] if t.get("result", {}).get("district")
    ]
    assert trace_districts and all("Maryvale" in str(d) for d in trace_districts)


def test_home_district_does_not_override_named():
    ctx = AgentContext(district="phoenix", date="2026-08-18", hour=14)
    profile = UserProfile.from_dict({"home_district": "maryvale"})
    out = plan_and_run("audit chicago", ctx, profile=profile)
    trace_districts = [
        t["result"]["district"] for t in out["trace"] if t.get("result", {}).get("district")
    ]
    assert trace_districts and all("Chicago" in str(d) for d in trace_districts)


def test_followup_resolves_last_district():
    ctx = AgentContext(district="phoenix", date="2026-08-18", hour=14)
    plan_and_run("audit chicago", ctx)
    assert ctx.last_district == "chicago"
    out = plan_and_run("what about its cost", ctx)
    trace_districts = [
        t["result"]["district"] for t in out["trace"] if t.get("result", {}).get("district")
    ]
    assert trace_districts and all("Chicago" in str(d) for d in trace_districts)


def test_fuzzy_district_typo():
    ctx = AgentContext(district="phoenix", date="2026-08-18", hour=14)
    out = plan_and_run("audit phoenex", ctx)
    trace_districts = [
        t["result"]["district"] for t in out["trace"] if t.get("result", {}).get("district")
    ]
    assert trace_districts and all("Phoenix" in str(d) for d in trace_districts)


def test_answer_has_tldr():
    ctx = AgentContext(district="phoenix", date="2026-08-18", hour=14)
    out = plan_and_run("audit phoenix", ctx)
    assert out["answer_tldr"]
    assert "Phoenix" in out["answer_tldr"]


def test_tldr_uses_profile_units():
    ctx = AgentContext(district="phoenix", date="2026-08-18", hour=14)
    profile = UserProfile.from_dict({"units": "f"})
    out = plan_and_run("audit phoenix", ctx, profile=profile)
    assert "°F" in out["answer_tldr"]
    assert "°C" not in out["answer_tldr"]


def test_personalization_intensity_line():
    ctx = AgentContext(district="phoenix", date="2026-08-18", hour=14)
    profile = UserProfile.from_dict({"intensity": "heavy"})
    out = plan_and_run("plan tomorrow for phoenix", ctx, profile=profile)
    assert "heavy-work" in out["answer"]


def test_unit_note_in_answer():
    ctx = AgentContext(district="phoenix", date="2026-08-18", hour=14)
    profile = UserProfile.from_dict({"units": "f"})
    out = plan_and_run("audit phoenix", ctx, profile=profile)
    assert "Unit preference: °F active" in out["answer"]


def test_plan_without_profile_unchanged():
    ctx = AgentContext(district="phoenix", date="2026-08-18", hour=14)
    out = plan_and_run("audit phoenix", ctx)
    assert "heavy-work" not in out["answer"]
    assert "Unit preference" not in out["answer"]