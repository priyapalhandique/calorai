"""Carbon & Grid Twin — cool-roof delta → kWh → CO2 tons + grid MW."""

from __future__ import annotations

from typing import Any

# US average grid: 0.4 kg CO2 per kWh, heat-induced grid peak ~ 1% per 1K city-wide delta (heuristic)
CO2_KG_PER_KWH = 0.4
GRID_MW_PER_K = 2.5  # heuristic: 1K city-wide cooling ≈ 2.5 MW peak shave for Phoenix scale


def carbon_block(delta_t_c: float | None, district: str = "phoenix") -> dict[str, Any]:
    if delta_t_c is None:
        return {"present": False, "reason": "no whatif delta"}
    # kWh per year for one 400m2 tile from retrofit_roi assumptions is not directly stored; proxy:
    # annual_saving_usd from whatif → kWh via $0.15/kWh
    # Instead compute directly: degree-hours proxy 2500h * 400m2 * delta_T * U(1.5) / COP(3) /1000
    dh = 2500.0  # hot city
    kwh_per_year = dh * 400.0 * abs(delta_t_c) * 1.5 / 3.0 / 1000.0
    co2_tons = kwh_per_year * CO2_KG_PER_KWH / 1000.0
    grid_mw = abs(delta_t_c) * GRID_MW_PER_K
    return {
        "present": True,
        "district": district,
        "delta_t_c": round(float(delta_t_c), 2),
        "kwh_per_year": round(kwh_per_year, 0),
        "co2_tons_per_year": round(co2_tons, 2),
        "grid_mw_peak_shave": round(grid_mw, 2),
        "assumptions": {"CO2_kg_per_kWh": CO2_KG_PER_KWH, "grid_MW_per_K": GRID_MW_PER_K, "degree_hours": dh},
        "note": "Grid twin: cool-roof cooling → kWh → CO2 + peak MW (heuristic, honest).",
    }
