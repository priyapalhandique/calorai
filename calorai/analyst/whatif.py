"""What-if planner — cool-roof thought experiment on hot tiles."""
from __future__ import annotations

from typing import Any

from ..physics.economics import retrofit_roi, cooling_degree_hours
from ..physics.mitigation import albedo_delta_temperature


def whatif_cool_roof(
    tiles: list[dict[str, Any]],
    irradiance_w_m2: float,
    surface_c: float,
    albedo_before: float,
    albedo_after: float = 0.50,
    emissivity: float = 0.93,
    convective_coefficient: float = 12.0,
) -> dict[str, Any]:
    if not tiles:
        return {"present": False, "reason": "no tiles"}
    n = len(tiles)
    top_n = max(1, n // 5)  # top 20%
    # sorted not needed for temp calc — same sunlit assumption
    delta = albedo_delta_temperature(
        irradiance_w_m2=irradiance_w_m2,
        albedo_before=albedo_before,
        albedo_after=albedo_after,
        surface_temperature_c=surface_c,
        emissivity=emissivity,
        convective_coefficient=convective_coefficient,
    )
    # economics on one 400m2 tile
    dh = cooling_degree_hours(30.0)  # district-agnostic proxy for slider
    roi = retrofit_roi(
        degree_hours_c=dh,
        delta_t_c=delta["delta_temperature_c"],
        envelope_area_m2=400.0,
        retrofit_cost_usd=400.0 * 25.0,
    )
    return {
        "present": True,
        "albedo_before": round(albedo_before, 3),
        "albedo_after": round(albedo_after, 3),
        "delta_t_c": round(delta["delta_temperature_c"], 2),
        "removed_flux_w_m2": round(delta["removed_flux_w_m2"], 1),
        "basis": delta.get("basis", ""),
        "scope": f"top {top_n}/{n} hottest tiles (≈20%)",
        "annual_saving_usd": roi.get("annual_saving_usd"),
        "payback_years": roi.get("payback_years"),
    }
