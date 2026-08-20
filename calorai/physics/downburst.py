"""Downburst thermodynamic diagnostic from the environment series.

Downbursts are violent surface outflows driven by evaporative cooling
of rain through dry sub-cloud air: the air is cooled so strongly it
sinks (negative buoyancy), hits the surface and spreads horizontally.
The essential precursor thermodynamics, per Caracena (1990) and
Wakimoto (1985), is a **large wet-bulb depression** (dry-bulb minus
wet-bulb temperature) coincident with precipitation: large D means the
rain has a big evaporation potential.

The FortyGuard environment series carries apparent temperature, wet-bulb
temperature, relative humidity and precipitation, so the diagnostic is
directly computable per hour:

    D = T_apparent - T_wet_bulb        (dry-bulb proxied by apparent)

Risk band (documented parameterization, Caracena 1990 Table):
    no precipitation in the trailing 3 h  -> low   (no trigger)
    precip & D < 8 K                      -> low
    precip & 8 K <= D < 14 K              -> medium
    precip & D >= 14 K                    -> high

Honesty contract: this is a *diagnostic* (which hours in the series
carried the thermodynamic signature of microburst genesis), not a
forecast — the series is the district's meso-scale environment, not a
storm-scale sounding, and apparent temperature proxies dry-bulb.
"""

from __future__ import annotations

from typing import Any

LOW_THRESHOLD_K = 8.0
HIGH_THRESHOLD_K = 14.0
PRECIP_TRIGGER_MM = 0.1
PRECIP_WINDOW_HOURS = 3


def _band(depression_k: float, precip_window_mm: float) -> str:
    if precip_window_mm < PRECIP_TRIGGER_MM:
        return "low"
    if depression_k < LOW_THRESHOLD_K:
        return "low"
    if depression_k < HIGH_THRESHOLD_K:
        return "medium"
    return "high"


def downburst_risk_series(env: dict[str, Any]) -> dict[str, Any]:
    """Per-hour downburst-risk diagnostic from an EnvSeries dict.

    Expects ``env`` with parallel lists ``apparent_c``, ``wet_bulb_c``,
    ``precipitation_mm`` (and optional ``hour``). Returns the risk
    series, the peak hour/band, and an advisory.
    """
    apparent = env.get("apparent_c") or []
    wet_bulb = env.get("wet_bulb_c") or []
    precip = env.get("precipitation_mm") or []
    hours = env.get("hour") or list(range(max(len(apparent), len(wet_bulb), len(precip))))
    if not apparent or not wet_bulb:
        return {"present": False}

    series: list[dict[str, Any]] = []
    for i, h in enumerate(hours):
        ta = apparent[i] if i < len(apparent) else apparent[-1]
        tw = wet_bulb[i] if i < len(wet_bulb) else wet_bulb[-1]
        p = precip[i] if i < len(precip) else 0.0
        if ta is None or tw is None:
            continue
        depression_k = max(ta - tw, 0.0)
        window = sum(
            precip[j] if j < len(precip) and precip[j] is not None else 0.0
            for j in range(max(0, i - PRECIP_WINDOW_HOURS + 1), i + 1)
        )
        risk = _band(depression_k, window)
        series.append(
            {
                "hour": h,
                "apparent_c": round(ta, 2),
                "wet_bulb_c": round(tw, 2),
                "depression_k": round(depression_k, 2),
                "precip_3h_mm": round(window, 2),
                "risk": risk,
            }
        )

    if not series:
        return {"present": False}
    ranks = {"low": 0, "medium": 1, "high": 2}
    peak = max(series, key=lambda s: (ranks[s["risk"]], s["depression_k"]))
    worst = ranks[peak["risk"]]
    advisory = {
        0: "No downburst signature: either dry air without rain, or rain without evaporation potential.",
        1: "Moderate downburst signature: rain falling through fairly dry air. "
        "Expect gusty outflow, gusts possibly 15-25 m/s above the mean wind.",
        2: "Strong downburst signature: rain falling through very dry air (D >= 14 K). "
        "Typical of dry-microburst environments; outflow gusts can exceed 25 m/s. "
        "Treat as a construction/outdoor-work weather hazard window.",
    }[worst]

    return {
        "present": True,
        "peak_hour": peak["hour"],
        "peak_depression_k": peak["depression_k"],
        "peak_risk": peak["risk"],
        "hours_high": sum(1 for s in series if s["risk"] == "high"),
        "hours_medium": sum(1 for s in series if s["risk"] == "medium"),
        "series": series,
        "advisory": advisory,
        "caveat": (
            "diagnostic, not forecast: meso-scale district environment, not a "
            "storm-scale sounding; apparent temperature proxies dry-bulb; "
            "bands are a documented parameterization of Caracena (1990) and "
            "Wakimoto (1985) wet-bulb-depression criteria."
        ),
    }


def outflow_watch_text(risk: str) -> str:
    return {
        "low": "No outflow hazard flagged from this series.",
        "medium": "Outflow risk: secure loose equipment; gusts may be strong near rain cells.",
        "high": "OUTFLOW WATCH: treat as a weather hazard window — halt elevated/crane "
        "work and secure lightweight structures during the flagged hours.",
    }.get(risk, "")