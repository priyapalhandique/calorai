"""Heat stress — translating temperature intelligence into human risk.

The API hands us the ingredients directly (wet-bulb, apparent
temperature); we combine them into the operational indices a heat
officer actually acts on:

    WBGT = 0.7 T_wb + 0.2 T_g + 0.1 T_db      (outdoor, sun)
    WBGT = 0.7 T_wb + 0.3 T_db                (no globe measurement)

with the classic work-rest bands from occupational heat guidance.
"""

from __future__ import annotations

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
) -> float:
    """Wet-bulb globe temperature (°C).

    Uses the 0.7/0.2/0.1 outdoor weighting when a globe (black-bulb)
    reading is available, otherwise the two-term approximation
    0.7 T_wb + 0.3 T_db.
    """
    if globe_celsius is None:
        return 0.7 * wet_bulb_celsius + 0.3 * dry_bulb_celsius
    return 0.7 * wet_bulb_celsius + 0.2 * globe_celsius + 0.1 * dry_bulb_celsius


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
) -> dict:
    """Combine WBGT band with heatmap exceedance duration.

    The heatmap ``exceedance`` layer reports hours-above-threshold per
    tile — the *duration* axis of exposure. This joins it with the
    *intensity* axis (WBGT) into a single risk verdict.
    """
    level = heat_stress_level(wbgt(wet_bulb_celsius, dry_bulb_celsius))
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
        "exceedance_hours_above_c": exceedance_hours,
        "threshold_c": threshold_celsius,
        "duration_risk": duration_risk,
        "overall_risk": overall,
    }