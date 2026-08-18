"""Heat stress — translating temperature intelligence into human risk.

The API hands us the ingredients directly (wet-bulb, apparent
temperature); we combine them into the operational indices a heat
officer actually acts on:

    WBGT = 0.7 T_wb + 0.2 T_g + 0.1 T_db      (outdoor, sun)

where the globe (black-bulb) temperature can be *estimated from the
solar load* when no globe station exists — the reason outdoor WBGT
jumps so fast when the sun comes out:

    T_g ≈ T_db + 0.03 · G (1 − 0.15 u)

with the classic work-rest bands from occupational heat guidance.
"""

from __future__ import annotations

import math


def humidex(air_temperature_c: float, relative_humidity_pct: float) -> float:
    """Canadian-style humidex (°C): T + 5/9·(e − 10), e in hPa.

    Equivalent comfort index to the US heat index; never reports below
    the air temperature (clamped).
    """
    if relative_humidity_pct < 0.0 or relative_humidity_pct > 100.0:
        raise ValueError("relative humidity must be in [0, 100]")
    e = (
        6.112
        * math.exp(17.62 * air_temperature_c / (243.12 + air_temperature_c))
        * relative_humidity_pct
        / 100.0
    )
    return max(air_temperature_c, air_temperature_c + 5.0 / 9.0 * (e - 10.0))


def globe_temperature_c(
    air_temperature_c: float,
    irradiance_w_m2: float,
    wind_speed_m_s: float = 0.0,
    coefficient: float = 0.03,
) -> float:
    """Estimated black-globe temperature (°C) from solar load.

    T_g = T_db + k · G · max(0, 1 − 0.15 u), k ≈ 0.03 °C·m²/W — a black
    globe in full sun runs 15–25 °C hotter than the air; wind deflates
    the reading.
    """
    if irradiance_w_m2 < 0.0:
        raise ValueError("irradiance cannot be negative")
    if wind_speed_m_s < 0.0:
        raise ValueError("wind speed cannot be negative")
    excess = coefficient * irradiance_w_m2 * max(0.0, 1.0 - 0.15 * wind_speed_m_s)
    return air_temperature_c + excess


#: WBGT bands (°C): (upper_bound, label, guidance).
#: Values below the first band are "minimal risk".
WBGT_BANDS: tuple[tuple[float, str, str], ...] = (
    (18.0, "minimal", "Continuous work with no restriction."),
    (22.0, "low", "Monitor; drink water regularly."),
    (26.0, "moderate", "Begin work-rest cycles; watch sensitive workers."),
    (29.0, "high", "Heavy work needs rest cycles; watch all workers."),
    (31.0, "very_high", "Limit heavy work; frequent rest in shade."),
    (float("inf"), "extreme", "Stop heavy outdoor work; emergency protocol."),
)


def wbgt(
    wet_bulb_celsius: float,
    dry_bulb_celsius: float,
    globe_celsius: float | None = None,
    irradiance_w_m2: float | None = None,
    wind_speed_m_s: float = 0.0,
) -> float:
    """Wet-bulb globe temperature (°C).

    Uses the 0.7/0.2/0.1 outdoor weighting when a globe (black-bulb)
    reading is available, otherwise estimates it from the solar load
    (``globe_temperature_c``), otherwise falls back to the two-term
    approximation 0.7 T_wb + 0.3 T_db.
    """
    if globe_celsius is None and irradiance_w_m2 is not None:
        globe_celsius = globe_temperature_c(
            dry_bulb_celsius, irradiance_w_m2, wind_speed_m_s
        )
    if globe_celsius is None:
        return 0.7 * wet_bulb_celsius + 0.3 * dry_bulb_celsius
    return 0.7 * wet_bulb_celsius + 0.2 * globe_celsius + 0.1 * dry_bulb_celsius


def heat_exposure_dose(
    wbgt_celsius: float,
    hours: float,
    threshold_celsius: float | None = None,
) -> dict:
    """Cumulative heat exposure (°C·h).

    ``wbgt_hours`` is the raw exposure; ``above_threshold_c_hours``
    (when a threshold is given, e.g. 31 °C) is the part of the shift
    spent past the safe band — the dose metric for worker-safety
    memos.
    """
    return {
        "wbgt_hours": round(wbgt_celsius * hours, 1),
        "threshold_c": threshold_celsius,
        "above_threshold_c_hours": (
            round(max(0.0, wbgt_celsius - threshold_celsius) * hours, 1)
            if threshold_celsius is not None
            else None
        ),
    }


def heat_stress_level(wbgt_celsius: float) -> dict:
    """Classify a WBGT reading into an actionable band."""
    for upper, label, guidance in WBGT_BANDS:
        if wbgt_celsius < upper:
            return {
                "wbgt_celsius": round(wbgt_celsius, 2),
                "level": label,
                "guidance": guidance,
            }
    return {
        "wbgt_celsius": round(wbgt_celsius, 2),
        "level": "extreme",
        "guidance": "Stop heavy outdoor work; emergency protocol.",
    }


def exposure_risk(
    wet_bulb_celsius: float,
    dry_bulb_celsius: float,
    exceedance_hours: float,
    threshold_celsius: float = 30.0,
    irradiance_w_m2: float | None = None,
    wind_speed_m_s: float = 0.0,
) -> dict:
    """Combine WBGT band with heatmap exceedance duration.

    The heatmap ``exceedance`` layer reports hours-above-threshold per
    tile — the *duration* axis of exposure. This joins it with the
    *intensity* axis (WBGT, globe estimated from solar when the load is
    given) into a single risk verdict, plus a cumulative dose.
    """
    wbgt_value = wbgt(
        wet_bulb_celsius,
        dry_bulb_celsius,
        irradiance_w_m2=irradiance_w_m2,
        wind_speed_m_s=wind_speed_m_s,
    )
    level = heat_stress_level(wbgt_value)
    duration_risk = (
        "low" if exceedance_hours < 3.0
        else "medium" if exceedance_hours < 8.0
        else "high"
    )
    if level["level"] in ("high", "very_high", "extreme") or duration_risk == "high":
        overall = "high"
    elif level["level"] in ("moderate",) or duration_risk == "medium":
        overall = "medium"
    else:
        overall = "low"
    return {
        **level,
        "wbgt_c": round(wbgt_value, 2),
        "exceedance_hours_above_c": exceedance_hours,
        "threshold_c": threshold_celsius,
        "duration_risk": duration_risk,
        "overall_risk": overall,
        "dose": heat_exposure_dose(
            wbgt_value,
            exceedance_hours,
            threshold_celsius=31.0,  # "very_high" band
        ),
    }