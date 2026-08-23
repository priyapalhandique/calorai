"""Industrial pollutants from heat signatures — chemical analysis proxy.

Heat drives chemistry: ozone formation is photochemical (heat + sunlight),
NOx/SO2 scale with industrial heat output, PM2.5 traps in canyons.
We estimate from heat signatures already computed (no new sensor):
- O3 (ozone) ~ base + f(T, irradiance, NOx proxy)
- NO2, PM2.5, SO2 scaled to industrial vs residential heat + canyon trapping

All diagnostic, honest: heat signature → pollutant proxy, not a monitor.
Sources: Seinfeld & Pandis *Atmospheric Chemistry*, EPA AQI breakpoints, Arrhenius.
"""

from __future__ import annotations

from typing import Any

import math


def _ozone_ppb(air_c: float, irradiance_w_m2: float, nox_proxy: float) -> float:
    # Seinfeld & Pandis simplified: O3 increases ~3 ppb per K above 25C + solar term
    base = 35.0  # ppb background
    t_term = max(0.0, air_c - 25.0) * 2.8  # ~2.8 ppb/K
    sun_term = max(0.0, irradiance_w_m2 - 400.0) / 900.0 * 18.0  # up to ~18 ppb at 1300 W/m2
    nox_term = nox_proxy * 0.3  # NOx feeds O3
    return base + t_term + sun_term + nox_term


def _aqi_band(pollutant: str, value: float) -> str:
    # Simplified EPA breakpoints
    if pollutant == "o3":
        if value <= 54:
            return "good"
        if value <= 70:
            return "moderate"
        if value <= 85:
            return "unhealthy for sensitive"
        if value <= 105:
            return "unhealthy"
        return "very unhealthy"
    if pollutant == "pm2.5":
        if value <= 12:
            return "good"
        if value <= 35.4:
            return "moderate"
        if value <= 55.4:
            return "unhealthy for sensitive"
        return "unhealthy"
    if pollutant == "no2":
        if value <= 53:
            return "good"
        if value <= 100:
            return "moderate"
        return "unhealthy"
    return "moderate"


def pollutants_block(report: dict[str, Any]) -> dict[str, Any]:
    snap = report.get("snapshot", {}) or {}
    atmos = report.get("atmosphere", {}) or {}
    landcover = report.get("landcover", {}) or {}
    heatwave = report.get("heatwave_landuse", {}) or {}
    is_industrial = heatwave.get("is_industrial", False)

    air_c = float(atmos.get("air_temperature_c") or snap.get("mean_c") or 30.0)
    irradiance = float(atmos.get("sky_temperature_c") or 0)  # placeholder; use diurnal solar if available
    # Prefer diurnal solar at audit hour
    diurnal = report.get("diurnal", {}) or {}
    solar_series = diurnal.get("solar_w_m2") or []
    hour = snap.get("hour", 14)
    if solar_series and isinstance(hour, int) and 0 <= hour < len(solar_series) and solar_series[hour] is not None:
        irradiance = float(solar_series[hour])

    # Industrial heat proxy: hot-core share + canyon h/w + max-mean
    hot_core = float((report.get("analysis", {}) or {}).get("equity", {}).get("hot_core_share_pct") or 5.0)
    h_w = float((report.get("canyon", {}) or {}).get("aspect_ratio_h_over_w") or 0.5)
    industrial_heat_score = min(1.0, hot_core / 25.0 * 0.5 + h_w / 1.5 * 0.5)
    base_no2 = 25.0 + (35.0 if is_industrial else 8.0) * industrial_heat_score
    base_pm25 = 12.0 + (22.0 if is_industrial else 6.0) * industrial_heat_score
    # Canyon trapping: high h/w traps PM2.5
    canyon_factor = 1.0 + max(0.0, h_w - 0.8) * 0.25
    pm25 = base_pm25 * canyon_factor
    no2 = base_no2 * (1.0 + max(0.0, air_c - 30.0) * 0.02)  # heat increases NOx chemistry
    so2 = 5.0 + (12.0 if is_industrial else 2.0) * industrial_heat_score
    o3 = _ozone_ppb(air_c, irradiance, no2 / 50.0)

    # Green mitigates: tree cover reduces PM2.5
    green = float(landcover.get("green_pct") or 0.0)
    if green > 10:
        pm25 *= 0.88
        o3 *= 0.95

    results = {
        "o3_ppb": round(o3, 1),
        "o3_band": _aqi_band("o3", o3),
        "no2_ppb": round(no2, 1),
        "no2_band": _aqi_band("no2", no2),
        "pm25_ug_m3": round(pm25, 1),
        "pm25_band": _aqi_band("pm2.5", pm25),
        "so2_ppb": round(so2, 1),
        "so2_band": "good",
    }
    # Top pollutant
    worst = max([("o3", o3, results["o3_band"]), ("pm2.5", pm25, results["pm25_band"]), ("no2", no2, results["no2_band"])], key=lambda x: x[1])

    return {
        "present": True,
        "district": report.get("district", ""),
        "landuse": heatwave.get("landuse", ""),
        "is_industrial": is_industrial,
        "heat_signature": {
            "max_c": snap.get("max_c"),
            "industrial_heat_score": round(industrial_heat_score, 3),
            "h_over_w": round(h_w, 2),
            "hot_core_share_pct": round(hot_core, 1),
        },
        "pollutants": results,
        "worst": {"pollutant": worst[0], "value": round(worst[1], 1), "band": worst[2]},
        "advisory": f"Heat-driven {worst[0]} {worst[2]} — {'industrial canyon traps PM2.5; add ventilation + shade' if worst[0]=='pm2.5' else 'ozone photochemistry; peak afternoon, limit outdoor exertion'}",
        "caveat": "Heat-signature proxy, not a monitor: O3 via Seinfeld & Pandis T+sun; NO2/PM2.5 scaled to industrial heat + canyon trapping, mitigated by green cover.",
    }
