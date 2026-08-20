"""M3 — wind-aware misting responder.

A misting plan is only as good as the air it sprays into. This module
turns the auditor's physics into an actionable spray schedule:

- **Evaporative efficiency** — misting cools by evaporation; humid air
  (small wet-bulb depression) evaporates slowly, so efficiency falls
  with humidity and the wet-bulb depression (same D the downburst
  diagnostic uses, opposite goal).
- **Drift / placement** — spray placed on the *upwind* side of the
  target drifts across it; the thermal-wind inflow axis (toward the hot
  core, the district's own circulation) is the natural drift lane.
  High ambient wind (>4 m/s) wastes spray — pause or switch to fine
  fogging in the lee.
- **Thermal relief** — evaporative cooling of sprayed air scales with
  (T_air − T_wb), capped by the sensible heat the water can absorb
  (latent heat of vaporization ~2.45 MJ/kg, documented).

Every number is returned with its assumption; misting is a decision
aid, not a physics claim about the full district energy balance.
"""

from __future__ import annotations

from typing import Any

LATENT_HEAT_VAP_J_KG = 2.45e6
#: sensible heat a misted air parcel can absorb per kg of water
WATER_COOLING_CAPACITY_KJ_KG = 2.45e3
HIGH_WIND_M_S = 4.0
LOW_EFFICIENCY_HUMIDITY_PCT = 60.0


def evaporative_efficiency(humidity_pct: float, wet_bulb_depression_k: float) -> float:
    """0..1 how well sprayed water evaporates in this air."""
    eff = 1.0 - min(humidity_pct, 100.0) / 100.0 * 0.6
    eff *= min(max(wet_bulb_depression_k / 12.0, 0.0), 1.0)
    return round(max(0.0, min(eff, 1.0)), 2)


def _inflow_label(direction_deg: float | None) -> str:
    if direction_deg is None:
        return "no dominant axis (uniform field)"
    labels = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
    return labels[int(round(direction_deg / 45.0)) % 8]


def misting_plan(
    wbgt_c: float,
    humidity_pct: float,
    wind_speed_m_s: float,
    air_temp_c: float,
    inflow_direction_deg: float | None,
    inflow_speed_scale_m_s: float = 0.0,
) -> dict[str, Any]:
    """A full misting recommendation for the audit hour."""
    depression_k = max(air_temp_c - _wet_bulb_from_humidity(air_temp_c, humidity_pct), 0.0)
    eff = evaporative_efficiency(humidity_pct, depression_k)
    wind = max(wind_speed_m_s, inflow_speed_scale_m_s)  # circulation adds to ambient

    if wbgt_c < 28.0 or air_temp_c < 28.0:
        level = "none"
        headline = "Conditions below the misting trigger — cooling demand is low."
        schedule = "No misting needed."
    elif eff < 0.25:
        level = "limited"
        headline = (
            f"Humid air ({humidity_pct:.0f}%) limits evaporative efficiency "
            f"({eff:.0f}%) — misting would mostly wet, not cool. Focus on shade "
            "and hydration instead."
        )
        schedule = "Standby; spot misting only in shade/shelter."
    elif wind > HIGH_WIND_M_S:
        level = "guard"
        headline = (
            f"Wind {wind:.1f} m/s would carry spray off target — pause line "
            "misting, use fine fog in sheltered corners."
        )
        schedule = "Paused (high drift); resume when wind eases."
    else:
        level = "active"
        headline = (
            f"WBGT {wbgt_c:.1f} °C, dry air, calm wind — misting is effective. "
            f"Place line emitters on the {_inflow_label(inflow_direction_deg)} "
            "side so the district's inflow drifts the spray across the core."
        )
        hours = f"{wbgt_c - 1.0:.0f}:00-{wbgt_c + 2.0:.0f}:00"
        schedule = f"Active window {hours} local; 30 s on / 90 s off cycles."

    # Water + energy estimate for an active/guard deployment (documented).
    if level in ("active", "guard"):
        water_m3_hr = round(0.05 * (1.0 + 0.5 * (1 - eff)), 3)
        energy_kwh_hr = round(water_m3_hr * 1000.0 * 0.02, 2)  # pump energy, documented
    else:
        water_m3_hr = 0.0
        energy_kwh_hr = 0.0

    return {
        "level": level,
        "headline": headline,
        "schedule": schedule,
        "evaporative_efficiency": eff,
        "wet_bulb_depression_k": round(depression_k, 2),
        "placement": _inflow_label(inflow_direction_deg),
        "inflow_direction_deg": inflow_direction_deg,
        "water_m3_per_hour": water_m3_hr,
        "energy_kwh_per_hour": energy_kwh_hr,
        "assumptions": {
            "latent_heat_of_vaporization": "2.45 MJ/kg",
            "efficiency": "humidity-limited (0.6 weight) x wet-bulb-depression ratio",
            "drift_threshold": "pause above 4 m/s ambient+circulation wind",
            "water": "0.05 m3/hr per line emitter scaled by (1 - efficiency)/2",
        },
        "caveat": (
            "decision aid for outdoor operations; not a district energy-balance "
            "claim. Verify local water pressure and air-quality rules before "
            "deployment."
        ),
    }


def _wet_bulb_from_humidity(air_temp_c: float, humidity_pct: float) -> float:
    """Documented proxy: wet-bulb = air temp - (100 - RH) * 0.06 (K).

    Mirrors the mock atmosphere's humidity-to-wet-bulb mapping so the
    depression is consistent with the district's env series.
    """
    return air_temp_c - max(0.0, (100.0 - humidity_pct)) * 0.06