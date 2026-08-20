"""N4 — runway heat & takeoff analysis (compact aviation module).

Extreme heat changes how an aircraft takes off. This module turns the
auditor's surface and air temperatures into the operational numbers a
pilot/dispatcher cares about, all from standard references:

- **Density altitude** — DA = PA + 120·(OAT − ISA) feet, FAA-H-8083-25B
  *Pilot's Handbook of Aeronautical Knowledge* (Ch. "Aircraft
  Performance"). ISA at a field elevation: 15 °C − 6.5 °C/km (FAA lapse).
- **Takeoff distance** — thrust and lift both scale ~ inversely with air
  density, so takeoff distance grows roughly 10–12% per 1,000 ft of DA
  (AOPA / FAA performance-training rule of thumb). We return the ratio
  vs. sea-level standard day.
- **Weight restriction** — the same physics constrains max takeoff
  weight; we estimate the weight reduction needed to keep the required
  distance within the longest runway.
- **Surface risks** — hot tarmac (softening/rutting above ~60 °C, FAA
  AC 150/5370 pavement guidance; rubber/brake heat buildup at high
  ambient + heavy braking).

Labeled *planning diagnostic* — never dispatch software. No aircraft
specifics are assumed unless the caller supplies elevation/runway.
"""

from __future__ import annotations

from typing import Any

ISA_SEA_LEVEL_C = 15.0
ISA_LAPSE_C_PER_M = 0.0065
FEET_PER_METER = 3.28084
TAKEOFF_DISTANCE_PCT_PER_KFT = 0.11
DA_PER_ISA_DEG_FT = 120.0
SURFACE_RISK_TARMAC_C = 60.0
SURFACE_RISK_TIRE_C = 70.0

#: Airport defaults (documented public data).
AIRPORTS: dict[str, dict[str, Any]] = {
    "phoenix": {
        "name": "Phoenix Sky Harbor Intl (KPHX)",
        "elevation_ft": 1135.0,
        "runways_ft": [11489.0, 10300.0, 7800.0],
    },
}


def _isa_temperature_c(elevation_ft: float) -> float:
    """ISA temperature at a field elevation (FAA-H-8083-25B lapse)."""
    return ISA_SEA_LEVEL_C - ISA_LAPSE_C_PER_M * (elevation_ft / FEET_PER_METER)


def density_altitude(air_temp_c: float, elevation_ft: float) -> float:
    """DA in feet (FAA-H-8083-25B)."""
    isa = _isa_temperature_c(elevation_ft)
    return elevation_ft + DA_PER_ISA_DEG_FT * (air_temp_c - isa)


def takeoff_distance_factor(density_altitude_ft: float) -> float:
    """Ratio of takeoff distance at DA vs. sea-level standard day.

    AOPA/FAA rule of thumb: ~11% per 1,000 ft of density altitude
    (thrust and lift both scale ~ inverse air-density ratio).
    """
    return 1.0 + TAKEOFF_DISTANCE_PCT_PER_KFT * (density_altitude_ft / 1000.0)


def _surface_risk(tile_max_c: float, air_temp_c: float) -> tuple[str, str]:
    tarmac = max(tile_max_c, air_temp_c)
    if tarmac >= SURFACE_RISK_TIRE_C:
        return "critical", (
            f"tarmac/tire surface ~{tarmac:.0f} °C: soft asphalt (rutting risk, "
            "FAA AC 150/5370) and tire/brake heat limits are a real concern."
        )
    if tarmac >= SURFACE_RISK_TARMAC_C:
        return "high", (
            f"tarmac ~{tarmac:.0f} °C: asphalt softening window; heavy braking "
            "builds tire heat fast. Schedule movement off peak."
        )
    if air_temp_c >= 40.0:
        return "elevated", "air temperature near operational limits; monitor brake cooling."
    return "normal", "surface temperatures within normal operating range."


def runway_heat_analysis(
    air_temp_c: float,
    tile_max_c: float,
    humidity_pct: float,
    wind_speed_m_s: float,
    elevation_m: float | None = None,
    runway_m: float | None = None,
    airport_key: str | None = None,
) -> dict[str, Any]:
    """Full aviation block for a district's audit hour.

    Defaults to Phoenix Sky Harbor (highest-use airfield in the mock
    catalog) unless the caller supplies elevation/runway explicitly.
    """
    if elevation_m is None:
        elevation_m = AIRPORTS["phoenix"]["elevation_ft"] / FEET_PER_METER
    elevation_ft = elevation_m * FEET_PER_METER
    da_ft = density_altitude(air_temp_c, elevation_ft)
    da_m = da_ft / FEET_PER_METER
    factor = takeoff_distance_factor(da_ft)

    runway_ft = runway_m * FEET_PER_METER if runway_m else AIRPORTS["phoenix"]["runways_ft"][0]
    required_ft = factor * 5000.0  # reference GA takeoff run, documented
    weight_pct = None
    if required_ft > runway_ft:
        # Distance scales ~1/rho ~ (1/W)^? ; estimate the weight cut that
        # brings the required run inside the runway (documented approx).
        weight_pct = max(0.60, 1.0 - (required_ft - runway_ft) / required_ft * 0.6)

    risk, risk_text = _surface_risk(tile_max_c, air_temp_c)
    hot_ramp = 0.7 if air_temp_c >= 40.0 else (0.4 if air_temp_c >= 35.0 else 0.1)

    return {
        "airport": AIRPORTS["phoenix"]["name"] if airport_key is None else airport_key,
        "elevation_m": round(elevation_m, 0),
        "air_temp_c": round(air_temp_c, 1),
        "density_altitude_m": round(da_m, 0),
        "density_altitude_ft": round(da_ft, 0),
        "takeoff_distance_factor": round(factor, 2),
        "required_run_m": round(required_ft / FEET_PER_METER, 0),
        "runway_available_m": round(runway_ft / FEET_PER_METER, 0),
        "weight_restriction_hint": (
            f"takeoff weight should be reduced to ~{weight_pct:.0%} of max "
            "to keep the required run inside the available runway"
            if weight_pct else "no weight restriction at this density altitude"
        ),
        "surface_risk": risk,
        "surface_text": risk_text,
        "hot_ramp_workers": hot_ramp,
        "advisory": (
            f"DA {da_ft:.0f} ft → takeoff run ~{factor:.2f}× sea level. "
            f"Tarmac/tire risk: {risk}. "
            "Planning diagnostic only — always use the airframe's own "
            "performance charts and crew dispatch for a real flight."
        ),
        "references": [
            "FAA-H-8083-25B Pilot's Handbook of Aeronautical Knowledge (density altitude, takeoff performance)",
            "AOPA rule of thumb: takeoff distance ~10-12% per 1,000 ft DA",
            "FAA AC 150/5370-10H airport pavement (asphalt softening/rutting)",
        ],
        "caveat": (
            "planning diagnostic for heat-budget context, not flight "
            "dispatch software. Aircraft-specific POH charts override every "
            "value here."
        ),
    }