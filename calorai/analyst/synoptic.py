"""Synoptic risk block — heat-wave-day / omega-block heat-dome / fire weather.

All from the 24-h env series already fetched (no extra API calls):
- Heat-wave day: sustained apparent >= threshold for >=3 consecutive hours + WBGT high.
- Omega-block / heat dome: subsidence subsidence signature — clear skies,
  high irradiance, high apparent temp, low cloud (=> subsidence).
- Fire weather: vapor pressure deficit (VPD) from RH + temp, dryness band.

Honest caveat: single-day analysis, no observed wind — fire index uses dryness
only; multi-day heat waves need multi-day pulls (offered as optional live mode).
"""

from __future__ import annotations

import math
from typing import Any


def _vpd_kpa(air_c: float, rh_pct: float) -> float:
    # Tetens saturation vapor pressure (kPa), then VPD = es*(1-RH/100)
    es = 0.6108 * math.exp(17.27 * air_c / (237.3 + air_c))
    return max(0.0, es * (1.0 - rh_pct / 100.0))


def synoptic_block(
    apparent_c: list[float | None] | None,
    humidity_pct: list[float | None] | None,
    solar_w_m2: list[float | None] | None,
    cloud_cover_pct: list[float | None] | None,
    wbgt_c: float | None,
    threshold_c: float = 30.0,
) -> dict[str, Any]:
    if not apparent_c or not any(v is not None for v in apparent_c):
        return {"present": False, "reason": "no diurnal apparent series"}

    n = len(apparent_c)
    # filter valid entries
    valid = [(i, v) for i, v in enumerate(apparent_c) if v is not None]
    if not valid:
        return {"present": False, "reason": "all apparent values None"}

    # heat-wave day: >= threshold for >=3 consecutive observed hours
    cur = 0
    best = 0
    for v in apparent_c:
        if v is not None and v >= threshold_c:
            cur += 1
            best = max(best, cur)
        else:
            cur = 0
    heat_wave_day = best >= 3 and (wbgt_c or 0) >= 26.0
    heat_wave_band = "high" if heat_wave_day and (wbgt_c or 0) >= 30 else ("moderate" if heat_wave_day else "low")

    # omega-block / heat dome: clear skies (cloud <=30%) + high solar (>= district median proxy 800) + hot
    # use provided arrays; if missing, fall back to not present
    dome_score = 0
    dome_detail: dict[str, Any] = {}
    if cloud_cover_pct and solar_w_m2:
        # count clear-sky hot hours
        clear_hot = 0
        for i in range(min(n, len(cloud_cover_pct), len(solar_w_m2))):
            ac = apparent_c[i]
            cc = cloud_cover_pct[i]
            sol = solar_w_m2[i]
            if ac is None or cc is None or sol is None:
                continue
            if cc <= 30.0 and sol >= 800.0 and ac >= threshold_c:
                clear_hot += 1
        dome_score = clear_hot
        dome_detail = {"clear_hot_hours": clear_hot}
        dome_band = "high" if clear_hot >= 6 else ("moderate" if clear_hot >= 3 else "low")
    else:
        dome_band = "unknown"

    # fire weather: VPD-based dryness band from max VPD in day
    vpd_vals: list[float] = []
    if humidity_pct:
        for i in range(min(n, len(humidity_pct))):
            ac = apparent_c[i]
            rh = humidity_pct[i]
            if ac is None or rh is None:
                continue
            vpd_vals.append(_vpd_kpa(float(ac), float(rh)))
    max_vpd = max(vpd_vals) if vpd_vals else 0.0
    mean_vpd = sum(vpd_vals) / len(vpd_vals) if vpd_vals else 0.0
    if max_vpd >= 4.0:
        fire_band = "high"
    elif max_vpd >= 2.5:
        fire_band = "moderate"
    else:
        fire_band = "low"

    return {
        "present": True,
        "heat_wave_day": heat_wave_day,
        "heat_wave_band": heat_wave_band,
        "longest_hot_stretch_hours": best,
        "dome_band": dome_band,
        "dome_detail": dome_detail,
        "fire_band": fire_band,
        "max_vpd_kpa": round(max_vpd, 2),
        "mean_vpd_kpa": round(mean_vpd, 2),
        "vpd_series_kpa": [round(v, 2) for v in vpd_vals] if vpd_vals else [],
        "caveat": "single-day, no observed wind; multi-day heat waves need multi-day pulls",
    }
